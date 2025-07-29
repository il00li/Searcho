<?php
// إعدادات البوت
define('BOT_TOKEN', '8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo');
define('PIXABAY_KEY', '51444506-bffefcaf12816bd85a20222d1');
define('CHANNELS', ['@crazys7','@AWU87']);
define('STATES_FILE', 'states.json');
define('SUBS_FILE', 'subscribers.json');

// استدعاء الدوال
function api($method, $params = []) {
    $url = "https://api.telegram.org/bot".BOT_TOKEN."/$method";
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $params
    ]);
    $res = curl_exec($ch);
    curl_close($ch);
    return json_decode($res, true);
}

function sendMessage($chat_id, $text, $keyboard = null) {
    $data = ['chat_id'=>$chat_id, 'text'=>$text, 'parse_mode'=>'HTML'];
    if ($keyboard) {
        $data['reply_markup'] = json_encode(['inline_keyboard'=>$keyboard]);
    }
    api('sendMessage', $data);
}

function sendPhoto($chat_id, $photo, $caption, $keyboard = null) {
    $data = ['chat_id'=>$chat_id, 'photo'=>$photo, 'caption'=>$caption];
    if ($keyboard) {
        $data['reply_markup'] = json_encode(['inline_keyboard'=>$keyboard]);
    }
    api('sendPhoto', $data);
}

function loadJson($file) {
    return file_exists($file) ? json_decode(file_get_contents($file), true) : [];
}

function saveJson($file, $data) {
    file_put_contents($file, json_encode($data, JSON_UNESCAPED_UNICODE));
}

function isSubscribed($user_id) {
    foreach (CHANNELS as $ch) {
        $res = api('getChatMember', ['chat_id'=>$ch, 'user_id'=>$user_id]);
        if (!$res['ok'] || !in_array($res['result']['status'], ['member','creator','administrator'])) {
            return false;
        }
    }
    return true;
}

function kbStart() {
    return [
        [['text'=>'👁 بدء البحث','callback_data'=>'start_search']],
        [['text'=>'🧸 أنواع البحث','callback_data'=>'choose_type']]
    ];
}

function kbTypes() {
    $types = ['illustration','photo','video','vector'];
    $rows = [];
    foreach ($types as $t) {
        $rows[] = [['text'=>"🧸 $t",'callback_data'=>"type_$t"]];
    }
    return $rows;
}

function kbNav() {
    return [
        [['text'=>'⬅️','callback_data'=>'prev'],['text'=>'➡️','callback_data'=>'next']],
        [['text'=>'🔒 اختيار','callback_data'=>'lock']]
    ];
}

function searchPixabay($q, $type) {
    $url  = "https://pixabay.com/api/?key=".PIXABAY_KEY."&q=".urlencode($q)."&image_type=$type";
    $res  = file_get_contents($url);
    $json = json_decode($res, true);
    return $json['hits'] ?? [];
}

// نقطة الدخول
$update = json_decode(file_get_contents('php://input'), true);
if (!$update) exit;

$states = loadJson(STATES_FILE);
$subs    = loadJson(SUBS_FILE);

// التعامل مع الرسائل
if (!empty($update['message'])) {
    $msg  = $update['message'];
    $cid  = $msg['chat']['id'];
    $uid  = $msg['from']['id'];
    $text = $msg['text'] ?? '';

    if ($text === '/start') {
        if (!isSubscribed($uid)) {
            $txt = "يرجى الاشتراك أولًا في القنوات:\n";
            foreach (CHANNELS as $c) $txt .= "• $c\n";
            sendMessage($cid, $txt, [[['text'=>'تحقّق | Check','callback_data'=>'verify']]]);
        } else {
            sendMessage($cid, "أهلاً بك، اختر العملية:", kbStart());
        }
        exit;
    }

    if (!empty($states[$uid]['awaiting'])) {
        $type    = $states[$uid]['type'] ?? 'photo';
        $results = searchPixabay($text, $type);
        if (empty($results)) {
            sendMessage($cid, "❌ لا توجد نتائج لـ \"$text\"", kbStart());
            unset($states[$uid]);
            saveJson(STATES_FILE, $states);
        } else {
            $states[$uid] = [
                'type'    => $type,
                'awaiting'=> false,
                'results' => $results,
                'index'   => 0
            ];
            saveJson(STATES_FILE, $states);
            $item = $results[0];
            sendPhoto($cid, $item['webformatURL'], $item['tags'], kbNav());
        }
        exit;
    }
}

// التعامل مع الأزرار
if (!empty($update['callback_query'])) {
    $cb   = $update['callback_query'];
    $cid  = $cb['message']['chat']['id'];
    $uid  = $cb['from']['id'];
    $data = $cb['data'];

    api('answerCallbackQuery',['callback_query_id'=>$cb['id']]);

    if ($data === 'verify') {
        if (isSubscribed($uid)) {
            sendMessage($cid, "✅ تم التحقق، اختر العملية:", kbStart());
        } else {
            sendMessage($cid, "❌ لم تشترك بعد.");
        }
        exit;
    }

    if ($data === 'choose_type') {
        sendMessage($cid, "اختر نوع البحث:", kbTypes());
        exit;
    }

    if (strpos($data,'type_') === 0) {
        $type = substr($data,5);
        $states[$uid]['type'] = $type;
        saveJson(STATES_FILE, $states);
        sendMessage($cid, "تم اختيار: $type", kbStart());
        exit;
    }

    if ($data === 'start_search') {
        $states[$uid]['awaiting'] = true;
        saveJson(STATES_FILE, $states);
        sendMessage($cid, "📥 أرسل كلمة البحث:");
        exit;
    }

    if (in_array($data,['next','prev'])) {
        $st = $states[$uid] ?? [];
        if (empty($st['results'])) {
            sendMessage($cid, "⚠️ لا توجد نتائج.", kbStart());
        } else {
            $i     = $st['index'];
            $total = count($st['results']);
            $i     = $data==='next'? $i+1: $i-1;
            if ($i<0) $i = $total-1;
            if ($i>=$total) $i = 0;
            $states[$uid]['index'] = $i;
            saveJson(STATES_FILE, $states);
            $item = $st['results'][$i];
            sendPhoto($cid, $item['webformatURL'], $item['tags'], kbNav());
        }
        exit;
    }

    if ($data === 'lock') {
        api('editMessageReplyMarkup', [
            'chat_id'    => $cid,
            'message_id' => $cb['message']['message_id']
        ]);
        sendMessage($cid, "✅ تم اختيار النتيجة. للبحث مجددًا: /start");
        unset($states[$uid]['results']);
        saveJson(STATES_FILE, $states);
        exit;
    }
}
