# Android On-Device AI Agent — Complete Development Guide

Everything you need to build an Android app that runs an AI agent on-device, controlling the phone through accessibility services.

This guide covers the full stack: on-device LLM (LiteRT-LM / Gemma), accessibility service patterns, tool calling, auto-reply systems, QA automation via ADB, permission UX, session management, and every pitfall along the way.

Not theory. Every section comes from real bugs, real fixes, real production code.

## 0. 術語 + 前提知識

### 術語
- **Package name** — Android app 嘅唯一 ID，例如 `com.example.myagent`。喺 `app/build.gradle` 嘅 `applicationId` 搵到。
- **AccessibilityService** — Android 系統級 service，可以讀/控制任何 app 嘅 UI（tap、type、read screen）。需要用戶授權。
- **ADB** — Android Debug Bridge，USB 連手機後用 command line 操作手機。`adb devices` check 連接。
- **LiteRT-LM** — Google 嘅 on-device LLM SDK（前身 MediaPipe LLM）。跑 Gemma model 喺手機上。
- **Engine** — LiteRT-LM 嘅 model instance。Load 一次，重複使用。食 RAM（2.3B model ≈ 2.6GB）。
- **Conversation** — Engine 上面嘅一個 chat session。有 system prompt + message history。一個 Engine 同一時間只能有一個 Conversation。Create 新 Conversation 會 close 舊嘅。
- **Tool calling** — LLM output 結構化嘅 function call（唔係 plain text）。例如 `tap(x=100, y=200)`。SDK 可以自動 parse + execute。
- **Prefill** — Model 處理 input tokens 嘅時間（system prompt + user message）。越長越慢。
- **SINGLE_TOP** — Android Intent flag。如果 Activity 已經喺 foreground，唔 create 新 instance，而係 call `onNewIntent()` 將新 intent 傳入。用於 broadcast trigger 重複 send task。
- **GSON** — Google 嘅 JSON library。Gradle dependency: `implementation 'com.google.code.gson:gson:2.10.1'`

### Gradle Dependencies
```gradle
// app/build.gradle
dependencies {
    implementation 'com.google.ai.edge.litertlm:litertlm-android:0.10.0'
    implementation 'com.google.code.gson:gson:2.10.1'
}
```

### 點搵你嘅 Package Name
```bash
# 方法 1：睇 build.gradle
grep "applicationId" app/build.gradle
# Output: applicationId "com.example.myagent"

# 方法 2：已安裝嘅 app
adb shell pm list packages | grep myagent
```

### 點搵你嘅 AccessibilityService class name
Full qualified name = package + class name。例如：
- Package: `com.example.myagent`
- Service class: `com.example.myagent.service.MyAccessibilityService`
- ADB 用嘅格式: `com.example.myagent/com.example.myagent.service.MyAccessibilityService`

### AccessibilityService 註冊（AndroidManifest.xml）
```xml
<!-- 喺 <application> 入面 -->
<service
    android:name=".service.YourAccessibilityService"
    android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
    android:exported="true">
    <intent-filter>
        <action android:name="android.accessibilityservice.AccessibilityService" />
    </intent-filter>
    <meta-data
        android:name="android.accessibilityservice"
        android:resource="@xml/accessibility_service_config" />
</service>
```

### Accessibility Config（res/xml/accessibility_service_config.xml）
```xml
<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeAllMask"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:accessibilityFlags="flagDefault|flagIncludeNotImportantViews|flagReportViewIds|flagRetrieveInteractiveWindows"
    android:canPerformGestures="true"
    android:canRetrieveWindowContent="true"
    android:canTakeScreenshot="true"
    android:notificationTimeout="100" />
```

### ADB 基本操作
```bash
# Check 手機有冇連接
adb devices -l

# Press Home
adb shell input keyevent KEYCODE_HOME

# Press Back
adb shell input keyevent KEYCODE_BACK

# Type text（空格用 %s）
adb shell "input text 'hello%sworld'"

# Tap 座標
adb shell input tap 540 960

# 開 app
adb shell am start -n com.example.myagent/com.example.myagent.ui.MainActivity

# Check app 有冇 running
adb shell pidof com.example.myagent
```

## 1. Build + Install + Test 一條龍

```bash
# Build
./gradlew assembleDebug 2>&1 | tail -3

# Install（唔好 force-stop，會 reset accessibility）
APK=$(find app/build/outputs/apk/debug/ -name "*.apk" | head -1) && adb install -r "$APK"

# ADB enable accessibility（唔使手動開）
adb shell settings put secure enabled_accessibility_services 'your.package/your.AccessibilityService'
adb shell settings put secure accessibility_enabled 1

# Check accessibility 狀態
adb shell dumpsys accessibility | grep "Bound\|Enabled\|Crashed"
```

**關鍵：唔好 `adb shell am force-stop`！** 會 reset accessibility service，要重新 enable。

## 2. 自動 Task Trigger（唔使手動 tap UI）

### BroadcastReceiver 方法（最可靠）
```java
// Register in AndroidManifest.xml
<receiver android:name=".debug.TaskTriggerReceiver" android:exported="true">
    <intent-filter><action android:name="your.package.TASK" /></intent-filter>
</receiver>

// Receiver launches activity with task extra
context.startActivity(new Intent(context, YourActivity.class)
    .putExtra("task", task)
    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP));

// Activity handles via onNewIntent (SINGLE_TOP re-delivery)
```

```bash
# Trigger task from ADB (goes through LLM)
adb shell "am broadcast -a your.package.TASK --es task 'do something' -p your.package"

# Auto-reply shortcuts (bypasses LLM, instant)
adb shell "am broadcast -a com.example.myagent.TASK --es task 'autoreply on Mom' -p com.example.myagent"
adb shell "am broadcast -a com.example.myagent.TASK --es task 'autoreply off' -p com.example.myagent"
```

### 重要：Activity 要 override onNewIntent
Install 之後 activity 可能已經 running，intent extra 唔會去 onCreate。一定要 onNewIntent。

## 3. 自動化 10x Testing

```bash
for run in $(seq 1 10); do
  adb logcat -c
  adb shell "am broadcast -a your.package.TASK --es task 'test task' -p your.package" > /dev/null
  PASS=false
  for i in $(seq 1 30); do
    sleep 5
    adb logcat -d | grep -q "SUCCESS_MARKER" && PASS=true && break
  done
  echo "RUN $run: $($PASS && echo ✅ || echo ❌)"
  sleep 20  # cooldown between runs
done
```

## 4. LiteRT-LM (Google On-Device LLM SDK)

### Engine 共享（避免 OOM）
```kotlin
// Singleton EngineHolder — 一個 Engine 可以有多個 Conversation
object EngineHolder {
    private var engine: Engine? = null
    fun getOrCreate(modelPath: String, cacheDir: String): Engine {
        if (engine == null) engine = Engine.create(modelPath, cacheDir)
        return engine!!
    }
}
```

### Native Tool Calling（v0.10.0+ work，冇 crash）
```kotlin
// 用 OpenApiTool interface
val tool = tool(object : OpenApiTool {
    override fun getToolDescriptionJsonString() = GSON.toJson(mapOf(
        "name" to "tool_name",
        "description" to "what it does",
        "parameters" to mapOf(...)
    ))
    override fun execute(params: String): String {
        // Your tool logic here
        return GSON.toJson(result)
    }
})

// Pass to ConversationConfig
val config = ConversationConfig(
    systemInstruction = Contents.of("system prompt"),
    initialMessages = emptyList(),
    tools = listOf(tool),
    samplerConfig = SamplerConfig(topK=64, topP=0.95, temp=0.7, seed=0),
    automaticToolCalling = false  // true = SDK auto-execute
)
```

### Response 處理
```kotlin
val response: Message = conversation.sendMessage(text, emptyMap())
// Native tool calls:
response.toolCalls  // List<ToolCall> with name + arguments
// Text response:
response.contents?.toString()
```

### Conversation 限制
- 一個 Engine 同一時間只能有一個 active Conversation
- 新 task 前 cancel 舊 task（否則 "Agent is already running"）
- sendMessage 連續 call 8+ 次可能 SIGSEGV（recreate conversation as workaround）

## 5. Accessibility Service Patterns

### 搵 UI Elements（Generic，唔靠 app-specific IDs）

```java
// 手動 tree traversal（比 findAccessibilityNodeInfosByText 更可靠）
void collectNodesWithText(AccessibilityNodeInfo node, String target, List<> results) {
    if (node == null) return;
    CharSequence text = node.getText();
    if (text != null && text.toString().toLowerCase().contains(target)) results.add(node);
    for (int i = 0; i < node.getChildCount(); i++)
        collectNodesWithText(node.getChild(i), target, results);
}

// 搵 bottommost EditText（message input，唔係 search bar）
// EditText className check（有啲 app isEditable() return false）
boolean isEditText = className != null && className.contains("EditText");

// Send button by contentDescription（多語言）
String[] keywords = {"send", "發送", "发送", "傳送", "전송", "enviar"};
```

### 等 App Window 切換
```java
boolean waitForActiveWindow(String packageName, long timeoutMs) {
    long deadline = System.currentTimeMillis() + timeoutMs;
    while (System.currentTimeMillis() < deadline) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root != null && packageName.equals(root.getPackageName().toString())) return true;
        Thread.sleep(500);
    }
    return false;
}
```

### Chatroom Detection（已經喺正確 chat？）
```java
// 搵 toolbar 區域（top 300px）有冇 contact name
collectTextNodesInRegion(root, 0, 300, candidates);
// 如果有 → skip navigation，直接 type
```

### Message Detection（Chatroom 開住時）
- `TYPE_NOTIFICATION_STATE_CHANGED` — app background 時（reliable）
- `TYPE_WINDOW_CONTENT_CHANGED` — chatroom open 時（需要 diff）
- Track fingerprint (contact:lastMessage) 防止重複 reply
- Reply 完 clear fingerprint 令下次 content change 重新 check

## 6. App Name → Package Name Resolver

```java
// Hardcoded common apps（全球一樣）
switch (name.toLowerCase()) {
    case "whatsapp": return "com.whatsapp";
    case "youtube": return "com.google.android.youtube";
    // ... 30+ apps
}
// Fallback: search installed apps by label
for (ApplicationInfo app : pm.getInstalledApplications(0)) {
    if (pm.getApplicationLabel(app).toString().equalsIgnoreCase(name)) return app.packageName;
}
```

## 7. Gemma 4 Tool Call Parsing（如果冇用 native API）

Gemma 4 E2B 會 output 至少 5 種 format：
1. `<tool_call>{"name":"tap","arguments":{"x":100}}</tool_call>`
2. `<|tool_call>call:tap{x:<|"|>100<|"|>}<tool_call|>`
3. `<|tool_call>call:open_app("WhatsApp")`（冇 closing tag）
4. `<tool_call>send_message{"contact":"Mom"}</tool_call>`（冇 "name" key）
5. Multi-tool: `{"name":"a"},{"name":"b"}`（comma separated）

需要：
- Auto-close missing braces
- `key:"value"` (colon+quotes) format
- `key="value"` (equals+quotes) format
- Balanced brace splitting for multi-tool
- Regex fallback for malformed JSON

**但如果用 native API（推薦），以上全部唔使。**

## 8. Debug Tips

```bash
# Screenshot
adb shell screencap -p /sdcard/s.png && adb pull /sdcard/s.png /tmp/s.png

# UI tree dump
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml /tmp/ui.xml

# Parse UI tree for specific elements
grep 'text="Mom"' /tmp/ui.xml

# Monitor specific log tags
adb logcat -d | grep "YourTag" | tail -10

# Check if accessibility crashed
adb shell dumpsys accessibility | grep "Crashed"

# Reset accessibility without force-stop
adb shell settings put secure enabled_accessibility_services ''
adb shell settings put secure enabled_accessibility_services 'your.package/your.Service'
```

## 9. Token 效率 + UI Automation（慳錢慳時間）

### uiautomator2 取代截圖（最重要）

截圖係 base64 圖片，幾千 token。改用 uiautomator2 text-based state check：

```python
import uiautomator2 as u2
d = u2.connect()  # 連 USB 設備

# ✅ 代替截圖：查元素存唔存在
d(text="Save").exists(timeout=3)        # bool
d(textContains="Connecting").wait_gone(30)  # 等消失

# ✅ 代替截圖：讀 screen 所有 text
texts = [el.text for el in d.xpath('//android.widget.TextView').all() if el.text]

# ✅ 代替截圖：完整 UI state（XML，幾十 token）
xml = d.dump_hierarchy(compressed=True, max_depth=20)

# ✅ 輸入文字（唔過 keyboard，無 autocorrect）
d(resourceId="pkg:id/etInput1").set_text("hello")

# ✅ 安全 click（唔存在唔 crash）
d.xpath('//android.widget.Button[@text="Save"]').click_exists(timeout=5)
```

截圖只係確認新 UI layout 時先用（final resort）。

### Send Button + EditText Overlap 問題

Telegram / 某些 app 嘅 Send button 同 EditText bounds 重疊。
Tap 落重疊區 → EditText 搶到 touch → 唔 send。

```python
# 查清楚邊界先
# EditText: [129,1926][888,2018]
# Send btn: [767,1923][992,2022]
# 安全 tap 點：x > EditText.right (888)，喺 Send btn 範圍內
d.click(950, 1972)  # x=950 係安全嘅
```

### Build Output
```bash
# 只睇最後 3 行（SUCCESS 或 error）
./gradlew assembleDebug 2>&1 | tail -3
```
唔好 read 完整 build output — 幾百行冇用。

### ADB Commands 要 Chain
```bash
# ✅ 好：1 個 Bash call
adb shell input keyevent KEYCODE_HOME && sleep 1 && \
adb shell screencap -p /sdcard/s.png && adb pull /sdcard/s.png /tmp/s.png
```

### .claudeignore（一次設置，永久節省）
```
# Project root 建呢個 file
build/
.gradle/
.idea/
*.apk
*.aab
```
避免 Claude 掃 generated files。

### Batch Edits Before Build
改晒所有 file → build 一次。唔好一個 edit 一個 build。

### Logcat 用 tag filter
```bash
# ✅ 好：filter specific tags
adb logcat -s TelegramHandler:I,ChannelManager:I -d | tail -10
```

## 10. QA / Self-Testing Workflow

### Step 1: Build + Install（冇 force-stop）
```bash
./gradlew assembleDebug 2>&1 | tail -3 && \
APK=$(find app/build/outputs/apk/debug/ -name "*.apk" | head -1) && \
adb install -r "$APK"
```

### Step 2: Enable Accessibility（ADB，唔使手動）
**CRITICAL: 每次 reinstall APK 後 Android 會 reset accessibility permission。一定要重新 enable。**
```bash
adb shell settings put secure enabled_accessibility_services 'com.example.myagent/com.example.myagent.service.MyAccessibilityService'
adb shell settings put secure accessibility_enabled 1
# Verify
adb shell settings get secure enabled_accessibility_services
```

### Step 3: Trigger Task（ADB broadcast，唔使手動 tap）
```bash
adb shell "am broadcast -a pkg.TASK --es task 'test task' -p pkg"
```

### Step 4: Monitor Result
```bash
adb logcat -c  # clear
# Poll for success/failure
for i in $(seq 1 20); do
  sleep 5
  adb logcat -d | grep -q "SUCCESS" && echo "PASS" && break
  adb logcat -d | grep -q "FAIL\|CRASH" && echo "FAIL" && break
done
```

### Step 5: Screenshot Verify
```bash
adb shell screencap -p /sdcard/result.png && adb pull /sdcard/result.png /tmp/result.png
# Read /tmp/result.png 用 Claude 嘅 image reading
```

### Step 6: 10x Reliability Test
```bash
for run in $(seq 1 10); do
  adb logcat -c
  adb shell "am broadcast ..." > /dev/null
  # ... monitor ...
  echo "RUN $run: PASS/FAIL"
  sleep 20
done
```

### Step 7: Timing Benchmark
```bash
START=$(date +%s)
# trigger task
# wait for completion
END=$(date +%s)
echo "$((END - START))s"
```

## 11. Debug 方法大全

### A. App 冇反應
```bash
# Check app 有冇 running
adb shell pidof your.package

# Check accessibility 有冇 crash
adb shell dumpsys accessibility | grep "Crashed"

# Check logcat errors
adb logcat -d | grep "Exception\|Error\|FATAL" | tail -10
```

### B. Accessibility Service 唔 Work
```bash
# Reset accessibility
adb shell settings put secure enabled_accessibility_services ''
sleep 1
adb shell settings put secure enabled_accessibility_services 'pkg/service'

# Verify root window
# 如果 getRootInActiveWindow() return null = service crashed
adb shell dumpsys accessibility | grep "Crashed"
```

### C. Tool Call 冇 Parse
```bash
# Check raw LLM response
adb logcat -d | grep "response.text=" | tail -5

# Check tool call count
adb logcat -d | grep "hasToolCalls\|toolCallCount" | tail -5

# Check parse errors
adb logcat -d | grep "Failed to parse\|regex fallback" | tail -5
```

### D. SendMessageTool 失敗
```bash
# Check each step
adb logcat -d | grep "SendMessageTool" | sed 's/.*SendMessageTool: //'
# Expected: Step 1 → Step 2 → Step 3 → Step 4 → Step 5: Sent!
```

### E. UI Element 搵唔到
```bash
# Dump full UI tree
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml /tmp/ui.xml

# Search for specific text
grep 'text="Mom"' /tmp/ui.xml

# Parse with Python for structured analysis
python3 -c "
import xml.etree.ElementTree as ET
for node in ET.parse('/tmp/ui.xml').iter('node'):
    text = node.get('text', '')
    bounds = node.get('bounds', '')
    if text: print(f'{bounds}: {text}')
"
```

### F. SIGSEGV / Native Crash
```bash
adb logcat -d | grep "SIGSEGV\|has died\|FATAL" | tail -5
# 如果係 LiteRT-LM crash：recreate conversation，唔好連續 sendMessage 太多次
```

### G. Task 卡住唔完成
```bash
# Check iteration count
adb logcat -d | grep "runAgentLoop iter=" | tail -5
# 如果 iter 好大但冇 tool call = LLM 唔識做嘢
# 如果 "Already replying" = 舊 task 未完成，要 cancel first
```

## 12. 避免嘅 Pitfalls

每個 pitfall 都有真實故事 — 我哋踩過，浪費咗時間，先學到。

### Pitfall 1: 唔好信 code comments
**故事：** Code 入面有一行 `// native tool API crashes on CPU backend (Google SDK bug)`。我哋信咗，寫咗 150 行 regex parser 做 workaround。最後試先知 native API 完全冇 crash — bug 可能從來唔存在或者早就 fix 咗。浪費成個 session。
**Rule：** Comment 係 claim 唔係 evidence。見到 "X doesn't work" → 先試 X。

### Pitfall 2: 唔好 force-stop app
**故事：** 每次 `adb shell am force-stop` 都 reset Android accessibility service settings 做 null。之後 accessibility 唔 work，app 乜都做唔到。搞咗好耐先發現。
**Rule：** 用 `adb install -r` 直接 reinstall，唔好 force-stop。如果一定要 force-stop，之後要重新 enable accessibility：
```bash
adb shell settings put secure enabled_accessibility_services 'pkg/service'
adb shell settings put secure accessibility_enabled 1
```

### Pitfall 3: findAccessibilityNodeInfosByText 唔可靠
**故事：** WhatsApp chat list 明明有 "Mom" 顯示，`findNodesByText("Mom")` 返 0 results。UI dump 證實 "Mom" 存在。原因不明（可能 window focus 問題）。
**Rule：** 唔好用 Android 嘅 `findAccessibilityNodeInfosByText`。自己寫 recursive tree traversal 搵 text nodes，100% 可靠。

### Pitfall 4: 新 task 前一定要 cancel 舊 task
**故事：** 10 次 test 得 2 次 pass。原因：舊 task 仲跑緊（LLM loop iteration 22），新 task 被 `if (running.get()) return` reject。加咗一行 `cancelCurrentTask()` → 10/10 pass。
**Rule：** `sendTask` 開頭一定要 cancel running task。

### Pitfall 5: BroadcastReceiver callback 唔 survive reinstall
**故事：** BroadcastReceiver 用 static callback 通知 Activity。Install 新 APK 後 Activity recreate，callback = null，broadcast 收到但冇人處理。
**Rule：** BroadcastReceiver 唔好用 callback。直接 launch Activity with intent extra + `FLAG_ACTIVITY_SINGLE_TOP`。Activity 用 `onNewIntent` 處理。

### Pitfall 6: WhatsApp 開住冇 notification
**故事：** Auto-reply 第一條 message work，第二條冇反應。原因：reply 完 WhatsApp chatroom 留喺前景，Android 唔 fire notification。
**Rule：** 兩條 detection path：
- `TYPE_NOTIFICATION_STATE_CHANGED` — app background（reliable）
- `TYPE_WINDOW_CONTENT_CHANGED` — chatroom open（需要 diff UI tree）

### Pitfall 7: WhatsApp EditText.isEditable() return false
**故事：** `collectEditableNodes` 用 `node.isEditable()` 搵 message input field。WhatsApp 嘅 EditText class 唔 report `isEditable=true`。搵唔到 input field = 打唔到字。
**Rule：** 同時 check `isEditable()` 同 `className.contains("EditText")`。

### Pitfall 8: LiteRT-LM Kotlin API 嘅 null parameter
**故事：** Java code call Kotlin constructor `ConversationConfig(sysPrompt, null, null, sampler)` — crash `NullPointerException: parameter initialMessages is non-null`。Kotlin 嘅 non-null parameter 喺 Java 入面冇 compile-time check。
**Rule：** Call Kotlin 嘅 constructor 時，所有 List/Map parameter 用 `emptyList()` / `emptyMap()`，唔好用 `null`。`sendMessage(text, null)` 一樣 crash — 用 `sendMessage(text, Collections.emptyMap())`。

### Pitfall 9: Input field hint "Message" 被當成 incoming message
**故事：** Content change detection 嘅 `findLastIncomingMessage` 搵到 "Message"（WhatsApp input field hint text）當成新 incoming message。Fingerprint 永遠係 `Mom:Message`，唔變，所以之後嘅真正新 message 被 skip。
**Rule：** Filter 走 common input hints：`"Message"`, `"Type a message"`, `"Type a message..."`。同時用 bounds 過濾：screen 底部 250px 嘅 text = input area，唔係 message。

### Pitfall 10: Gemma 4 E2B 嘅 tool call format 極度唔穩定
**故事：** 同一個 model 每次 output 唔同 format 嘅 tool call — 有時 JSON，有時 Gemma native tokens，有時冇 closing tag，有時逗號分隔多個 tool call，有時 tool name 後面直接跟 JSON（冇 "name" key）。總共 5+ 種 format。
**Rule：** 如果用 prompt-based tool calling，需要 5+ 個 parser pattern。**但最好用 native API** — SDK 自動 parse，唔使你搞。

### Pitfall 11: Multi-tool JSON split 用 indexOf("},{") 會截斷
**故事：** LLM output `{"name":"a","arguments":{"x":1}},{"name":"b"}`。用 `indexOf("},{") + 1` split → 得到 `{"name":"a","arguments":{"x":1}` — 少咗最後嘅 `}`！因為 nested braces。
**Rule：** 用 balanced brace counting 搵第一個 JSON object 嘅 end position。

### Pitfall 12: LLM response text-only = task complete (wrong)
**故事：** LLM 有時返文字唔返 tool call（"I apologize, I can't..."）。Agent loop 以為 task 完成。但其實 LLM 只係唔識做，唔代表完成。
**Rule：** 只有 response 包含 "finish"/"done"/"completed" 先算完成。其他 text-only response → re-prompt："Continue the task. Use a tool call."

### Pitfall 13: open_app("WhatsApp") 搵唔到 package
**故事：** LLM call `open_app("WhatsApp")` 但 tool 要求 `package_name` 參數 = `"com.whatsapp"`。"WhatsApp" 唔係 package name = fail。
**Rule：** OpenAppTool 要有 app name → package name resolver。30+ common apps hardcoded + fallback search by `PackageManager.getApplicationLabel`。

## 13. 完整 Flow（由零開始做一個 on-device AI agent app）

如果你係全新嘅 AI，唔識任何嘢，跟呢個順序：

### Phase 1: 基礎設施
1. Android project with Gradle（Android Studio 或 command line）
2. 加 LiteRT-LM dependency 到 `app/build.gradle`（見 Section 0）
3. 寫 EngineHolder singleton（見 Section 4）— 一個 Engine 共用，避免 OOM
4. 寫 AccessibilityService extends `android.accessibilityservice.AccessibilityService`
   - Override `onAccessibilityEvent(event)` — 處理 notification / content change
   - Override `onServiceConnected()` — service 啟動時 setup
   - `getRootInActiveWindow()` — 取得當前 screen 嘅 UI tree（任何 app）
   - `performGlobalAction(GLOBAL_ACTION_HOME/BACK)` — 按 Home/Back
   - `performGesture(GestureDescription)` — tap/swipe 任意座標
5. Register accessibility service in manifest（見 Section 0 嘅 XML）
6. 寫 LlmClient 用 native tool calling API（見 Section 4）

### Phase 2: Basic Tools
1. GetScreenInfoTool — read accessibility tree
2. TapTool — tap(x, y)
3. InputTextTool — type text into focused field
4. OpenAppTool — open app by name (with resolver)
5. FinishTool — signal task completion

### Phase 3: High-Level Tools
1. SendMessageTool — open messaging app → find contact → type → send
2. Generic pattern: open app → wait for window → find element → interact → verify

### Phase 4: Auto-Reply / Background Agent
1. Listen `TYPE_NOTIFICATION_STATE_CHANGED` for incoming messages
2. Listen `TYPE_WINDOW_CONTENT_CHANGED` for chatroom-open detection
3. LLM generate reply with conversation context
4. SendMessageTool or fast-path (type directly in open chatroom)
5. Debounce + own-message tracking to prevent loops

### Phase 5: Testing
1. BroadcastReceiver for ADB trigger
2. onNewIntent for SINGLE_TOP re-delivery
3. 10x reliability test script
4. Timing benchmark script
5. Screenshot verification

### Phase 6: Optimization
1. System prompt compression (minimize tokens)
2. Screen data compression (center coordinates, not full bounds)
3. Tool description compression
4. sendCount threshold for conversation recreate
5. Cancel old task before new task

### Phase 7: Permission UX (learned 2026-04-08)
1. Check ALL required permissions BEFORE starting a feature (not after)
2. If missing → Toast + navigate to app's Settings page (not grey chat text, not system settings directly)
3. Settings page must show each permission with live Connected/Disabled status
4. After user enables permission in system settings → auto-return to app's Settings page via onServiceConnected/onListenerConnected
5. NotificationListenerService has a stale toggle bug: after reinstall, system shows "enabled" but service not bound. Detect with `isConnected()` (static instance check) and tell user to toggle OFF→ON
6. Monitor workflow needs BOTH Accessibility Service AND NotificationListenerService. Check both before starting.

### Phase 8: LiteRT-LM Session Management (learned 2026-04-08)
1. **One session at a time**: LiteRT-LM Engine only supports 1 active Conversation. Chat UI and task agent cannot hold sessions simultaneously.
2. **onBeforeTask callback**: AppViewModel.startTask() must signal the chat UI to close its conversation before the task agent creates one. Pattern: `appViewModel.onBeforeTask = { conversation?.close(); conversation = null }`
3. **Retry with backoff**: LocalLlmClient.createConversation() should retry 5x with 1.5s backoff — the chat UI's conversation may still be closing.
4. **GPU→CPU fallback**: GPU inference can fail at runtime (OpenCL not found) even if model loads OK on GPU. Detect OpenCL errors in chat() and auto-fallback: close engine → recreate with Backend.CPU().
5. **gpuFailed flag**: Once GPU fails, remember it for the session. Don't retry GPU on every call.

### Phase 9: Task Auto-Return (learned 2026-04-08)
1. After in-app task completes (Channel.LOCAL), auto-navigate back to the chat Activity using FLAG_ACTIVITY_NEW_TASK + FLAG_ACTIVITY_SINGLE_TOP
2. SINGLE_TOP preserves the existing Activity instance — chat messages, session state all intact
3. Monitor tasks should NOT auto-return or press Home. They run in background. User stays in app.
4. NotificationListenerService catches notifications regardless of which app is in foreground — no need to leave the app for monitor to work.

### Phase 10: QA-First Development (learned 2026-04-08)
1. **Design QA tests BEFORE writing code**, not after
2. **QA_CHECKLIST.md**: permanent file, every test case has unique ID, format: `- [ ] **ID. Name**: step → expected → step → expected`
3. **Think like a human user**: "I tap send" not "sendChat() called". Cover wrong taps, leaving mid-task, missing permissions, first-time vs returning user.
4. **Per change**: new tests + affected existing tests. Per major feature: full checklist run.
5. **ADB-based E2E**: use `adb shell input tap/text`, `adb shell am broadcast`, uiautomator dump, logcat grep. No mocks.
6. **Accessibility check via ADB**: `adb shell settings get secure enabled_accessibility_services` — verify after every reinstall.
7. **QA debug changelog**: record `[date] [PASS/FAIL/ISSUE] ID description` in QA_CHECKLIST.md after each run.

### Phase 11: Project Tracking (learned 2026-04-08)
1. **CLAUDE.md** — project rules (QA-first, architecture-first, logging)
2. **QA_CHECKLIST.md** — permanent E2E test cases + debug changelog
3. **BACKLOG.md** — features, bugs, ideas with P0-P3 priority
4. **CLAUDE.local.md** — current session state (ephemeral)
5. When user mentions any new feature/bug/idea → write to BACKLOG.md immediately

### Phase 12: Community Management (learned 2026-04-08)
1. Reddit comments: scrape via `.json` suffix on any Reddit URL (free, no auth for read)
2. Reply via Reddit internal API (`/api/comment` + modhash) from Chrome DevTools browser context
3. Get modhash: `fetch('/api/me.json')` → `data.modhash`
4. QA verify every reply: `fetch('/api/info.json?id=COMMENT_ID')` → check `parent_id` matches
5. Safety: 3s delay between posts, vary content, mix with natural behavior
6. Always show Chinese summary of replies to Nicole before posting

## 14. Pitfalls Continued (learned 2026-04-08)

### Pitfall 14: Accessibility "starting..." message on every chat
**Story:** sendTask() checked accessibility service BEFORE keyword routing. Every message (including "monitor Mom") triggered "Accessibility service starting, please wait..." even when accessibility wasn't needed yet.
**Rule:** Route keywords FIRST (monitor/auto-reply bypass LLM entirely), then check accessibility only for tasks that actually need phone control.

### Pitfall 15: Floating button loses state when switching apps
**Story:** EasyFloat overlay's show() callback only set `isShowing = true` but didn't restore the UI state (RUNNING/IDLE/etc). When user switched to WhatsApp and back, floating button reverted to IDLE even though task was still running.
**Rule:** In the show() callback, always call `updateStateView(view, currentState)` to restore the visual state.

### Pitfall 16: Auto-return fires on EVERY service connect
**Story:** Added auto-return to Settings page in onServiceConnected/onListenerConnected. But this fires on every app start, not just when user manually enables permission. User sees unexpected navigation to Settings page on normal app launch.
**Rule:** Auto-return should ideally only fire during the permission flow. Consider a flag like `isInPermissionFlow` to gate the behavior. (Known issue, not yet fixed.)

### Pitfall 17: NotificationListener stale toggle after reinstall
**Story:** User reinstalled app. System settings showed Notification Access "enabled" but `isConnected()` returned false. Monitor started but never received notifications. User thought everything was set up correctly.
**Rule:** Always check `MyNotificationListener.isConnected()` (static instance), not just the system setting. If setting shows enabled but not connected, tell user to toggle OFF→ON.
