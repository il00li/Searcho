<?php
date_default_timezone_set('Asia/Riyadh');

##########################
##  إعدادات البوت
##########################

$BOT_TOKEN   = '8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo';  // استبدل بالتوكن الجديد لو جددته
$ADMIN_ID    = 7251748706;
$API_KEY     = '51444506-bffefcaf12816bd85a20222d1';
$CHANNELS    = ['@crazys7', '@AWU87'];

##########################
##  حالات المستخدمين
##########################

$userSearchType   = [];  // نوع البحث لكل مستخدم
$userResults      = [];  // نتائج Pixabay لكل مستخدم
$userStates       = [];  // flags: waiting_for_query, current_index

##########################
##  حلقة الاستماع للتحديثات
##########################

$offset = 0;
while (true) {
    $updates = getUpdates($offset);
    foreach ($updates as $upd) {
        $offset = $upd['update_id'] + 1;
        handleUpdate($upd);
    }
    sleep(1);
}

##########################
##  جلب التحديثات (long polling)
##########################

function getUpdates($offset)
{
    global $BOT_TOKEN;
    $url = "https://api.telegram.org/bot{$BOT_TOKEN}/getUpdates?timeout=30&offset={$offset}";
    $res = file_get_contents($url);
    $data = json_decode($res, true);
    return $data['ok'] ? $data['result'] : [];
}

##########################
##  التعامل مع كل تحديث
##########################

function handleUpdate($upd)
{
    global $userStates;

    if (isset($upd['message']) && isset($upd['message']['text'])) {
        $msg    = $upd['message'];
        $chatId = $msg['chat']['id'];
        $userId = $msg['from']['id'];
        $text   = $msg['text'];

        // /start
        if ($text === '/start') {
            handleStart($chatId, $userId, $upd['message']['message_id']);
            return;
        }

        // استقبال كلمة البحث
        if (!empty($userStates[$userId]['waiting_for_query'])) {
            handleQuery($chatId, $userId, $text);
            return;
        }
    }

    if (isset($upd['callback_query'])) {
        handleCallback($upd['callback_query']);
    }
}

##########################
##  أمر /start
##########################

function handleStart($chatId, $userId, $messageId)
{
    global $CHANNELS;

    if (!isUserSubscribed($userId)) {
        $txt = "⚠️ اشترك أولاً في القنوات التالية:";
        foreach ($CHANNELS as $ch) {
            $txt .= "\n• {$ch}";
        }
        sendMessage($chatId, $txt, [
            'inline_keyboard' => [[
                ['text' => "تحقق | Check", 'callback_data' => 'verify']
            ]]
        ]);
    } else {
        sendMessage($chatId, "مرحبا بك 👋 اختر أحد الخيارات:", [
            'inline_keyboard' => [
                [['text' => "👁 بدء البحث",   'callback_data' => 'start_search']],
                [['text' => "🧸 انواع البحث", 'callback_data' => 'select_type']],
            ]
        ]);
    }
}

##########################
##  التحقق من الاشتراك
##########################

function isUserSubscribed($userId)
{
    global $BOT_TOKEN, $CHANNELS;

    foreach ($CHANNELS as $ch) {
        $resp = file_get_contents(
            "https://api.telegram.org/bot{$BOT_TOKEN}/getChatMember"
            . "?chat_id={$ch}&user_id={$userId}"
        );
        $j = json_decode($resp, true);
        if (!$j['ok'] ||
            !in_array($j['result']['status'], ['member','administrator','creator'])
        ) {
            return false;
        }
    }
    return true;
}

##########################
##  التعامل مع callback_query
##########################

function handleCallback($cq)
{
    global $userSearchType, $userStates;

    $data   = $cq['data'];
    $chatId = $cq['message']['chat']['id'];
    $msgId  = $cq['message']['message_id'];
    $userId = $cq['from']['id'];

    answerCallback($cq['id']);

    if ($data === 'verify') {
        handleStart($chatId, $userId, $msgId);
        return;
    }

    if ($data === 'select_type') {
        $keys = [];
        foreach (['illustration','photo','video','vector'] as $t) {
            $keys[] = [['text' => "🧸 {$t}", 'callback_data' => "type_{$t}"]];
        }
        sendMessage($chatId, "اختر نوع البحث:", [
            'inline_keyboard' => $keys
        ]);
        return;
    }

    if (strpos($data, 'type_') === 0) {
        $type = substr($data, 5);
        $userSearchType[$userId] = $type;
        editMessageText(
            $chatId, $msgId,
            "✅ تم اختيار نوع البحث: {$type}"
        );
        return;
    }

    if ($data === 'start_search') {
        $userStates[$userId]['waiting_for_query'] = true;
        sendMessage($chatId, "📥 أرسل كلمة البحث الآن:");
        return;
    }

    // تنقل النتائج
    if (in_array($data, ['next','prev'])) {
        $dir = $data === 'next' ? +1 : -1;
        $userStates[$userId]['current_index'] =
            ($userStates[$userId]['current_index'] + $dir + count($GLOBALS['userResults'][$userId]))
            % count($GLOBALS['userResults'][$userId]);
        showResult($chatId, $msgId, $userId);
        return;
    }

    if ($data === 'lock') {
        // إزالة الأزرار
        editMessageReplyMarkup($chatId, $msgId);
        sendMessage($chatId, "✅ تم اختيار هذه النتيجة.\n🔄 لإعادة البحث: /start");
        return;
    }
}

##########################
##  استقبال كلمة البحث
##########################

function handleQuery($chatId, $userId, $query)
{
    global $API_KEY, $userSearchType, $userResults, $userStates;

    $type = $userSearchType[$userId] ?? 'illustration';
    $url  = "https://pixabay.com/api/?key={$API_KEY}"
          . "&q=" . urlencode($query)
          . "&image_type={$type}";

    $resp = file_get_contents($url);
    $j    = json_decode($resp, true);
    $hits = $j['hits'] ?? [];

    if (empty($hits)) {
        sendMessage($chatId, "❌ لم يتم العثور على نتائج ل\"{$query}\"");
        $userStates[$userId]['waiting_for_query'] = false;
        return;
    }

    $userResults[$userId]      = $hits;
    $userStates[$userId]       = [
        'waiting_for_query' => false,
        'current_index'     => 0
    ];

    showResult($chatId, null, $userId);
}

##########################
##  عرض النتيجة الحالية
##########################

function showResult($chatId, $msgId, $userId)
{
    global $userResults, $userStates;

    $idx    = $userStates[$userId]['current_index'];
    $item   = $userResults[$userId][$idx];
    $url    = $item['webformatURL'] ?? null;
    $caption = $item['tags'] ?? '';

    $keyboard = [
        [
            ['text' => '⬅️', 'callback_data' => 'prev'],
            ['text' => '➡️', 'callback_data' => 'next']
        ],
        [
            ['text' => 'اختيار 🔒', 'callback_data' => 'lock']
        ]
    ];

    // إذا اتينا من callback نعدل الرسالة، وإلا نرسل جديدة
    if ($msgId) {
        editMessageMedia($chatId, $msgId, $url, $caption, $keyboard);
    } else {
        sendPhoto($chatId, $url, $caption, $keyboard);
    }
}

##########################
##  دوال مساعدة للتواصل مع Telegram API
##########################

function sendMessage($chatId, $text, $replyMarkup = null)
{
    global $BOT_TOKEN;
    $payload = [
        'chat_id' => $chatId,
        'text'    => $text,
        'parse_mode' => 'HTML'
    ];
    if ($replyMarkup) {
        $payload['reply_markup'] = json_encode($replyMarkup);
    }
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/sendMessage?" .
        http_build_query($payload)
    );
}

function sendPhoto($chatId, $photoUrl, $caption = '', $replyMarkup = null)
{
    global $BOT_TOKEN;
    $payload = [
        'chat_id' => $chatId,
        'photo'   => $photoUrl,
        'caption' => $caption,
        'parse_mode' => 'HTML'
    ];
    if ($replyMarkup) {
        $payload['reply_markup'] = json_encode($replyMarkup);
    }
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/sendPhoto?" .
        http_build_query($payload)
    );
}

function answerCallback($callbackId)
{
    global $BOT_TOKEN;
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/answerCallbackQuery?" .
        http_build_query(['callback_query_id' => $callbackId])
    );
}

function editMessageText($chatId, $messageId, $text)
{
    global $BOT_TOKEN;
    $params = [
        'chat_id'    => $chatId,
        'message_id' => $messageId,
        'text'       => $text,
        'parse_mode' => 'HTML'
    ];
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageText?" .
        http_build_query($params)
    );
}

function editMessageMedia($chatId, $messageId, $mediaUrl, $caption, $keyboard)
{
    global $BOT_TOKEN;
    $media = [
        'type'    => 'photo',
        'media'   => $mediaUrl,
        'caption' => $caption,
        'parse_mode' => 'HTML'
    ];
    $payload = [
        'chat_id'    => $chatId,
        'message_id' => $messageId,
        'media'      => json_encode($media),
        'reply_markup' => json_encode($keyboard)
    ];
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageMedia?" .
        http_build_query($payload)
    );
}

function editMessageReplyMarkup($chatId, $messageId)
{
    global $BOT_TOKEN;
    file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageReplyMarkup?" .
        http_build_query([
            'chat_id'    => $chatId,
            'message_id' => $messageId
        ])
    );
}
