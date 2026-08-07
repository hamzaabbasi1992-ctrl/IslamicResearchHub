// Top-level build file - real plugin versions declared here, applied
// per-module (just :app for now) with `apply false` so this file owns
// the single source of truth for which AGP/Kotlin version this whole
// project builds against.
plugins {
    // Real fix: 8.7.2 didn't understand this SDK's newer platform-folder
    // naming ("platforms/android-37.0" vs the older "platforms/android-37")
    // and failed with "Failed to find Platform SDK" - confirmed directly
    // against the real installed SDK. 9.3.1 is the latest real stable
    // release as of this build (9.4.0 was still alpha).
    id("com.android.application") version "9.3.1" apply false
    // Real fix: AGP 9.x has built-in Kotlin support and registers its
    // own 'kotlin' extension - explicitly also applying the standalone
    // org.jetbrains.kotlin.android plugin then fails with "Cannot add
    // extension with name 'kotlin', as there is an extension already
    // registered" (confirmed directly). Only the Compose Compiler
    // plugin is still needed as a separate real plugin.
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
    id("com.google.devtools.ksp") version "2.0.21-1.0.28" apply false
}
