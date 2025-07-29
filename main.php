<?php
declare(strict_types=1);
date_default_timezone_set('Asia/Riyadh');

// جلب المتغيرات من البيئة (أو ضع القيم الصريحة إذا لزم)
$BOT_TOKEN   = getenv('BOT_TOKEN') ?: '8071576925:AAGgx_Jkuu-mRpjdMKiOQCDkkVQskXQYhQo';
$API_KEY     = getenv('API_KEY')   ?: '51444506-bffefcaf12816bd85a20222d1';
$ADMIN_ID    = (int)(getenv('ADMIN_ID') ?: 7251748706);
$CHANNELS    = ['@crazys7', '@AWU87'];

// حالات المستخدمين
$userStates     = []; // [userId => ['waiting_query'=>bool, 'current_index'=>int]]
$userSearchType = []; // [userId => 'illustration'|'photo'|'video'|'vector']
$userResults    = []; // [userId => hits array]

// بدء long polling
$offset = 0;
while (true) {
    $updates = getUpdates($offset);
    foreach ($updates as $upd) {
        $offset = (int)$upd['update_id'] + 1;
        handleUpdate($upd);
    }
    sleep(1);
}

// جلب التحديثات
function getUpdates(int $offset): array
{
    global $BOT_TOKEN;
    $resp = @file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/getUpdates?offset={$offset}&timeout=30"
    );
    $data = json_decode($resp ?: '', true);
    return $data['result'] ?? [];
}

// التعامل مع تحديث وحيد
function handleUpdate(array $upd): void
{
    if (isset($upd['message'])) {
        handleMessage($upd['message']);
    }
    if (isset($upd['callback_query'])) {
        handleCallback($upd['callback_query']);
    }
}

// التعامل مع الرسائل
function handleMessage(array $msg): void
{
    global $userStates;
    $chatId = $msg['chat']['id'];
    $userId = $msg['from']['id'];
    $text   = $msg['text'] ?? '';

    if ($text === '/start') {
        cmdStart($chatId, $userId);
        return;
    }

    if (!empty($userStates[$userId]['waiting_query'])) {
        processQuery($chatId, $userId, trim($text));
    }
}

// أمر /start
function cmdStart(int $chatId, int $userId): void
{
    global $CHANNELS, $userStates;
    $userStates[$userId]['waiting_query'] = false;

    if (!isUserSubscribed($userId)) {
        $keyboard = [[['text'=>'تحقق | Check','callback_data'=>'verify']]];
        $text = "⚠️ اشترك أولاً في هذه القنوات:\n" . implode("\n", array_map(fn($c)=>"• $c", $CHANNELS));
        sendMessage($chatId, $text, $keyboard);
    } else {
        $keyboard = [
            [['text'=>'👁 بدء البحث','callback_data'=>'start_search']],
            [['text'=>'🧸 أنواع البحث','callback_data'=>'select_type']],
        ];
        sendMessage($chatId, 'أهلاً بك 👋 اختر:', $keyboard);
    }
}

// فحص الاشتراك في القنوات
function isUserSubscribed(int $userId): bool
{
    global $BOT_TOKEN, $CHANNELS;
    foreach ($CHANNELS as $channel) {
        $resp = @file_get_contents(
            "https://api.telegram.org/bot{$BOT_TOKEN}/getChatMember"
            . "?chat_id={$channel}&user_id={$userId}"
        );
        $data = json_decode($resp ?: '', true);
        if (empty($data['ok']) ||
            !in_array($data['result']['status'], ['member','creator','administrator'])
        ) {
            return false;
        }
    }
    return true;
}

// التعامل مع الأزرار (CallbackQuery)
function handleCallback(array $cq): void
{
    global $userStates, $userSearchType;
    $data      = $cq['data'];
    $chatId    = $cq['message']['chat']['id'];
    $msgId     = $cq['message']['message_id'];
    $userId    = $cq['from']['id'];

    answerCallback($cq['id']);

    return match (true) {
        $data === 'verify'      => cmdStart($chatId, $userId),
        $data === 'select_type' => showTypeOptions($chatId),
        str_starts_with($data, 'type_')     => setSearchType($chatId, $msgId, $userId, $data),
        $data === 'start_search'            => startSearch($chatId, $userId),
        in_array($data,['next','prev'])     => navResults($cq, $data),
        $data === 'lock'                    => lockResult($chatId, $msgId),
        default                            => null,
    };
}

// عرض أنواع البحث
function showTypeOptions(int $chatId): void
{
    $types = ['illustration','photo','video','vector'];
    $keyboard = array_map(fn($t)=>[['text'=>"🧸 $t",'callback_data'=>"type_$t"]], $types);
    sendMessage($chatId, 'اختر نوع البحث:', $keyboard);
}

// تعيين نوع البحث
function setSearchType(int $chatId, int $msgId, int $userId, string $data): void
{
    global $userSearchType;
    $type = substr($data, 5);
    $userSearchType[$userId] = $type;
    editMessageText($chatId, $msgId, "✅ تم اختيار: $type");
}

// بدء البحث
function startSearch(int $chatId, int $userId): void
{
    global $userStates;
    $userStates[$userId]['waiting_query'] = true;
    sendMessage($chatId, '📥 أرسل كلمة البحث:');
}

// معالجة كلمة البحث
function processQuery(int $chatId, int $userId, string $query): void
{
    global $API_KEY, $userSearchType, $userResults, $userStates;
    $type = $userSearchType[$userId] ?? 'illustration';
    $url  = "https://pixabay.com/api/?key={$API_KEY}&q=" . urlencode($query) . "&image_type={$type}";

    $resp = @file_get_contents($url);
    $data = json_decode($resp ?: '', true);
    $hits = $data['hits'] ?? [];

    if (empty($hits)) {
        sendMessage($chatId, "❌ لا توجد نتائج لكلمة: «{$query}» [$type]");
        $userStates[$userId]['waiting_query'] = false;
        return;
    }

    $userResults[$userId] = $hits;
    $userStates[$userId]  = ['waiting_query'=>false,'current_index'=>0];
    showResult($chatId, null, $userId);
}

// عرض نتيجة واحدة
function showResult(int $chatId, ?int $msgId, int $userId): void
{
    global $userResults, $userStates;
    $idx   = $userStates[$userId]['current_index'];
    $item  = $userResults[$userId][$idx];
    $photo = $item['webformatURL'] ?? '';
    $caption = $item['tags'] ?? '';

    $keyboard = [
        [
            ['text'=>'⬅️','callback_data'=>'prev'],
            ['text'=>'➡️','callback_data'=>'next'],
        ],
        [
            ['text'=>'اختيار 🔒','callback_data'=>'lock']
        ]
    ];

    if ($msgId !== null) {
        editMessageMedia($chatId, $msgId, $photo, $caption, $keyboard);
    } else {
        sendPhoto($chatId, $photo, $caption, $keyboard);
    }
}

// التنقل بين النتائج
function navResults(array $cq, string $dir): void
{
    global $userResults, $userStates;
    $chatId = $cq['message']['chat']['id'];
    $msgId  = $cq['message']['message_id'];
    $userId = $cq['from']['id'];

    $total = count($userResults[$userId] ?? []);
    if ($total === 0) {
        sendMessage($chatId, 'لا توجد نتائج حالياً.');
        return;
    }

    $step = $dir === 'next' ? 1 : -1;
    $idx = ($userStates[$userId]['current_index'] + $step + $total) % $total;
    $userStates[$userId]['current_index'] = $idx;

    showResult($chatId, $msgId, $userId);
}

// قفل النتيجة وإزالة الأزرار
function lockResult(int $chatId, int $msgId): void
{
    editMessageReplyMarkup($chatId, $msgId);
    sendMessage($chatId, "✅ تم اختيار هذه النتيجة.\n🔄 لإعادة البحث: /start");
}

// دوال مساعدة للتواصل مع Telegram API

function sendMessage(int $chatId, string $text, array $keyboard = null): void
{
    global $BOT_TOKEN;
    $payload = ['chat_id'=>$chatId,'text'=>$text,'parse_mode'=>'HTML'];
    if ($keyboard) {
        $payload['reply_markup'] = json_encode(['inline_keyboard'=>$keyboard]);
    }
    @file_get_contents("https://api.telegram.org/bot{$BOT_TOKEN}/sendMessage?" . http_build_query($payload));
}

function sendPhoto(int $chatId, string $photo, string $caption, array $keyboard = null): void
{
    global $BOT_TOKEN;
    $payload = ['chat_id'=>$chatId,'photo'=>$photo,'caption'=>$caption,'parse_mode'=>'HTML'];
    if ($keyboard) {
        $payload['reply_markup'] = json_encode(['inline_keyboard'=>$keyboard]);
    }
    @file_get_contents("https://api.telegram.org/bot{$BOT_TOKEN}/sendPhoto?" . http_build_query($payload));
}

function answerCallback(string $callbackId): void
{
    global $BOT_TOKEN;
    @file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/answerCallbackQuery?"
      . http_build_query(['callback_query_id'=>$callbackId])
    );
}

function editMessageText(int $chatId, int $msgId, string $text): void
{
    global $BOT_TOKEN;
    @file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageText?"
      . http_build_query([
            'chat_id'=>$chatId,
            'message_id'=>$msgId,
            'text'=>$text,
            'parse_mode'=>'HTML'
        ])
    );
}

function editMessageMedia(int $chatId, int $msgId, string $media, string $caption, array $keyboard): void
{
    global $BOT_TOKEN;
    $mediaArr = ['type'=>'photo','media'=>$media,'caption'=>$caption,'parse_mode'=>'HTML'];
    $payload = [
        'chat_id'=>$chatId,
        'message_id'=>$msgId,
        'media'=>json_encode($mediaArr),
        'reply_markup'=>json_encode(['inline_keyboard'=>$keyboard])
    ];
    @file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageMedia?" . http_build_query($payload)
    );
}

function editMessageReplyMarkup(int $chatId, int $msgId): void
{
    global $BOT_TOKEN;
    @file_get_contents(
        "https://api.telegram.org/bot{$BOT_TOKEN}/editMessageReplyMarkup?"
      . http_build_query(['chat_id'=>$chatId,'message_id'=>$msgId])
    );
}
