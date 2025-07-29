<?php
// ========================================
// index.php — Telegram Bot + Pixabay API
// ========================================

// إعدادات البوت
define('BOT_TOKEN', '8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo');
define('PIXABAY_KEY', '51444506-bffefcaf12816bd85a20222d1');
define('CHANNELS', ['@crazys7','@AWU87']);
define('STATES_FILE', 'states.json');
define('SUBS_FILE', 'subscribers.json');

// دالة تواصل مع Telegram API
function api($method, $params = []) {
    $url = "https://api.telegram.org/bot".BOT_TOKEN."/$method";
    $ch  = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $params
    ]);
    $res = curl_exec($ch);
    curl_close($ch);
    return json_decode($res, true);
}

// إذا دخلت للملف مع ?set_webhook=1 فهنفذ تسجيل الـ Webhook
if (isset($_GET['set_webhook']) && $_GET['set_webhook'] === '1') {
    // عدّل هذا الرابط إلى رابط تطبيقك على Render
    $webhookUrl = 'https://searcho-ze20.onrender.com/index.php';
    $result     = api('setWebhook', ['url' => $webhookUrl]);
    header('Content-Type: application/json');
    echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

// دوال مساعدة للإرسال والتحميل
function send($chat, $text, $kb = null) {
    $data = ['chat_id'=>$chat, 'text'=>$text, 'parse_mode'=>'HTML'];
    if ($kb) $data['reply_markup'] = json_encode(['inline_keyboard'=>$kb]);
    api('sendMessage', $data);
}
function sendPhoto($chat, $photo, $caption, $kb = null) {
    $data = ['chat_id'=>$chat, 'photo'=>$photo, 'caption'=>$caption];
    if ($kb) $data['reply_markup'] = json_encode(['inline_keyboard'=>$kb]);
    api('sendPhoto', $data);
}
function load($file) {
    return file_exists($file) ? json_decode(file_get_contents($file), true) : [];
}
function save($file, $data) {
    file_put_contents($file, json_encode($data, JSON_UNESCAPED_UNICODE));
}
function isSub($uid) {
    foreach (CHANNELS as $ch) {
        $r = api('getChatMember', ['chat_id'=>$ch, 'user_id'=>$uid]);
        if (!$r['ok'] || !in_array($r['result']['status'], ['member','creator','administrator'])) {
            return false;
        }
    }
    return true;
}

// لوحات الأزرار
function kbStart() {
    return [
        [['text'=>'👁 بدء البحث','callback_data'=>'start_search']],
        [['text'=>'🧸 أنواع البحث','callback_data'=>'choose_type']]
    ];
}
function kbTypes() {
    return array_map(fn($t)=>[['text'=>"🧸 $t",'callback_data'=>"type_$t"]], 
        ['illustration','photo','video','vector']
    );
}
function kbNav() {
    return [
        [['text'=>'⬅️','callback_data'=>'prev'], ['text'=>'➡️','callback_data'=>'next']],
        [['text'=>'🔒 اختيار','callback_data'=>'lock']]
    ];
}

// بحث في Pixabay
function searchPixabay($q, $type) {
    $url = "https://pixabay.com/api/?key=".PIXABAY_KEY
         . "&q=".urlencode($q)
         . "&image_type=$type";
    $j   = json_decode(file_get_contents($url), true);
    return $j['hits'] ?? [];
}

// نقطة الدخول: استقبال التحديثات من Telegram
$update = json_decode(file_get_contents('php://input'), true);
if (!$update) exit;

$states = load(STATES_FILE);

// التعامل مع الرسائل النصية
if (!empty($update['message'])) {
    $m    = $update['message'];
    $cid  = $m['chat']['id'];
    $uid  = $m['from']['id'];
    $txt  = $m['text'] ?? '';

    if ($txt === '/start') {
        if (!isSub($uid)) {
            $msg = "📢 يرجى الاشتراك في القنوات التالية:\n";
            foreach (CHANNELS as $c) $msg .= "• $c\n";
            send($cid, $msg, [[['text'=>'تحقّق | Check','callback_data'=>'verify']]]);
        } else {
            send($cid, "✅ تم التحقق، اختر العملية:", kbStart());
        }
        exit;
    }

    // استقبال كلمة البحث
    if (!empty($states[$uid]['awaiting'])) {
        $type = $states[$uid]['type'] ?? 'photo';
        $res  = searchPixabay($txt, $type);
        if (empty($res)) {
            send($cid, "❌ لم يتم العثور على نتائج لـ \"$txt\"", kbStart());
            unset($states[$uid]);
            save(STATES_FILE, $states);
        } else {
            $states[$uid] = [
                'type'     => $type,
                'awaiting' => false,
                'results'  => $res,
                'index'    => 0
            ];
            save(STATES_FILE, $states);
            $item = $res[0];
            sendPhoto($cid, $item['webformatURL'], $item['tags'], kbNav());
        }
        exit;
    }
}

// التعامل مع الأزرار
if (!empty($update['callback_query'])) {
    $q   = $update['callback_query'];
    $cid = $q['message']['chat']['id'];
    $uid = $q['from']['id'];
    $d   = $q['data'];
    api('answerCallbackQuery', ['callback_query_id'=>$q['id']]);

    if ($d === 'verify') {
        if (isSub($uid)) send($cid, "✅ تم التحقق، اختر العملية:", kbStart());
        else send($cid, "❌ لم تشترك بعد.");
        exit;
    }

    if ($d === 'choose_type') {
        send($cid, "اختر نوع البحث:", kbTypes());
        exit;
    }

    if (strpos($d, 'type_') === 0) {
        $type = substr($d, 5);
        $states[$uid]['type'] = $type;
        save(STATES_FILE, $states);
        send($cid, "✅ نوع البحث المختار: $type", kbStart());
        exit;
    }

    if ($d === 'start_search') {
        $states[$uid]['awaiting'] = true;
        save(STATES_FILE, $states);
        send($cid, "📥 أرسل كلمة البحث:");
        exit;
    }

    if (in_array($d, ['next','prev'])) {
        $st = $states[$uid] ?? [];
        if (empty($st['results'])) {
            send($cid, "⚠️ لا توجد نتائج حالياً.", kbStart());
            exit;
        }
        $i     = $st['index'];
        $total = count($st['results']);
        $i     = ($d === 'next') ? $i + 1 : $i - 1;
        if ($i < 0)      $i = $total - 1;
        if ($i >= $total) $i = 0;
        $states[$uid]['index'] = $i;
        save(STATES_FILE, $states);
        $item = $st['results'][$i];
        sendPhoto($cid, $item['webformatURL'], $item['tags'], kbNav());
        exit;
    }

    if ($d === 'lock') {
        api('editMessageReplyMarkup', [
            'chat_id'    => $cid,
            'message_id' => $q['message']['message_id']
        ]);
        send($cid, "✅ تم اختيار النتيجة.\nلبحث جديد، أرسل /start");
        unset($states[$uid]['results']);
        save(STATES_FILE, $states);
        exit;
    }
}
