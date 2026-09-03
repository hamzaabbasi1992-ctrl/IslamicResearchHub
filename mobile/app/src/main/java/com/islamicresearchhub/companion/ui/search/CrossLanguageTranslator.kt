package com.islamicresearchhub.companion.ui.search

import android.content.Context
import org.json.JSONObject

object CrossLanguageTranslator {
    private var dictionary: Map<String, List<String>>? = null

    @Synchronized
    fun init(context: Context) {
        if (dictionary != null) return
        val dictMap = mutableMapOf<String, List<String>>()
        try {
            context.assets.open("cross_language_dict.json").use { inputStream ->
                val jsonString = inputStream.bufferedReader().use { it.readText() }
                val jsonObject = JSONObject(jsonString)
                val keys = jsonObject.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    val array = jsonObject.getJSONArray(key)
                    val list = mutableListOf<String>()
                    for (i in 0 until array.length()) {
                        list.add(array.getString(i))
                    }
                    dictMap[key.lowercase().trim()] = list
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        dictionary = dictMap
    }

    /**
     * Given a raw user query string (e.g. "prayer" or "fasting"),
     * returns a list of mapped Arabic/Urdu translation terms.
     */
    fun expandQuery(context: Context, query: String): List<String> {
        init(context)
        val normalizedKey = query.lowercase().trim()
        val dict = dictionary ?: return emptyList()

        val results = mutableSetOf<String>()
        dict[normalizedKey]?.let { results.addAll(it) }

        // Also check partial word matches for multi-word queries
        val words = normalizedKey.split("\\s+".toRegex())
        if (words.size > 1) {
            for (w in words) {
                dict[w]?.let { results.addAll(it) }
            }
        }
        return results.toList()
    }
}
