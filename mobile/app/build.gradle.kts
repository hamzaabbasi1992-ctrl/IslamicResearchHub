plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.islamicresearchhub.companion"
    // Matches the one real platform image the desktop's Android SDK has
    // installed (F:\android studio downloads\platforms\android-37.0) -
    // a higher compileSdk would force an extra SDK Manager download.
    compileSdk = 37

    defaultConfig {
        applicationId = "com.islamicresearchhub.companion"
        // Android 8.0 - a real, modern floor (current Compose/Room both
        // support well below this) without carrying legacy compat shims
        // for versions with negligible real remaining install share.
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // `kotlinOptions {}` was the org.jetbrains.kotlin.android plugin's
    // own DSL - removed along with that plugin (AGP 9.x's built-in
    // Kotlin support reads the Kotlin JVM target from `compileOptions`
    // above directly; confirmed by this real script-compilation error
    // once the plugin providing that block was removed).

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.8.5")

    // Room, real SQLite - both the catalog and per-book package
    // databases are pre-built SQLite files the desktop's export CLI
    // tools produce; Room opens them via `createFromFile()` rather
    // than creating/migrating a schema of its own from scratch.
    implementation("androidx.room:room-runtime:2.8.4")
    implementation("androidx.room:room-ktx:2.8.4")
    ksp("androidx.room:room-compiler:2.8.4")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
