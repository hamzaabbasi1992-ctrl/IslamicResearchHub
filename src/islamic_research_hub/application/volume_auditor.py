"""
Volume Auditor & Quality Gate Module for Islamic Research Hub
Provides automated per-volume quality auditing and auto-healing of truncated text snippets.
"""

import sqlite3
import json
import re

SENTENCE_TERMINATORS = ['۔', '؟', '!', '”', '"', 'آمین']

class VolumeAuditor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def audit_and_heal_volume(self, book_id: int, vol_num: int) -> dict:
        """
        Audits all confirmed EventCandidates for a given book_id.
        Auto-heals truncated stories ending mid-sentence by fetching contiguous page text.
        Returns a comprehensive audit metric dictionary.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT EventCandidateID, ChunkStartPage, ChunkEndPage, Title, ExtractedDataJson
            FROM EventCandidates
            WHERE BookID=? AND Status='confirmed'
            ORDER BY EventCandidateID
        """, (book_id,))
        candidates = cur.fetchall()

        if not candidates:
            conn.close()
            return {
                'book_id': book_id,
                'vol_num': vol_num,
                'total_candidates': 0,
                'healed_candidates': 0,
                'avg_length': 0,
                'sentence_integrity': 100.0,
                'status': 'PASSED (Empty Volume)'
            }

        healed_count = 0
        total_chars = 0
        complete_endings = 0

        for cid, sp, ep, title, data_json in candidates:
            data = json.loads(data_json) if data_json else {}
            matn = (data.get('quoted_excerpt') or data.get('background') or '').strip()

            # Check if text ends abruptly without sentence terminator
            if matn and not any(matn.endswith(ch) for ch in SENTENCE_TERMINATORS):
                # AUTO-HEAL: Fetch page ep and ep+1 text to complete the sentence
                cur.execute("SELECT Content FROM Pages WHERE BookID=? AND PageNo BETWEEN ? AND ?", (book_id, ep, ep + 1))
                page_rows = cur.fetchall()
                full_text = "\n".join(r[0] or '' for r in page_rows)

                # Find where matn started in page_text
                match_pos = full_text.find(matn[:40])
                if match_pos != -1:
                    sub_story = full_text[match_pos:]
                    # Find next proper sentence terminator
                    term_indices = [sub_story.find(ch) for ch in SENTENCE_TERMINATORS if sub_story.find(ch) != -1]
                    if term_indices:
                        first_term = min(term_indices)
                        healed_matn = sub_story[:first_term + 1].strip()
                        healed_matn = re.sub(r'</?urh1>', '', healed_matn).strip()
                        
                        if len(healed_matn) > len(matn):
                            data['quoted_excerpt'] = healed_matn
                            data['background'] = healed_matn
                            cur.execute("UPDATE EventCandidates SET ExtractedDataJson=? WHERE EventCandidateID=?", (json.dumps(data, ensure_ascii=False), cid))
                            matn = healed_matn
                            healed_count += 1

            total_chars += len(matn)
            if any(matn.endswith(ch) for ch in SENTENCE_TERMINATORS):
                complete_endings += 1

        conn.commit()
        conn.close()

        avg_len = total_chars // len(candidates)
        integrity = (complete_endings / len(candidates)) * 100.0

        return {
            'book_id': book_id,
            'vol_num': vol_num,
            'total_candidates': len(candidates),
            'healed_candidates': healed_count,
            'avg_length': avg_len,
            'sentence_integrity': round(integrity, 1),
            'status': 'PASSED' if integrity >= 70.0 else 'WARN'
        }

    def print_audit_report(self, audit_res: dict):
        """Prints a clean ASCII audit summary table for the volume."""
        print(f"\n=======================================================")
        print(f" AUTOMATED QUALITY AUDIT REPORT -- VOLUME {audit_res['vol_num']} (BookID {audit_res['book_id']})")
        print(f"=======================================================")
        print(f" * Total Waqiat Extracted  : {audit_res['total_candidates']}")
        print(f" * Auto-Healed Truncations : {audit_res['healed_candidates']}")
        print(f" * Average Story Length    : {audit_res['avg_length']} characters")
        print(f" * Sentence Integrity Pass : {audit_res['sentence_integrity']}%")
        print(f" * Quality Audit Verdict   : {audit_res['status']}")
        print(f"=======================================================\n")
