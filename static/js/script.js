$(function() {

    const socket = io();

/********* グローバル変数 ******************/
    let id = $("#id").html();           // ルームid

    const audio = $('#btn_audio')[0];   // オーディオ設定

    let timerID;

    let resetTime = 5000;               // いいね数のリセット時間

/****************************************/

    $('#roomid').val(id);

    // 接続者数の更新
    socket.on('count_update', function (msg) {
        let user = msg.name;
        // 人数の更新
        $('#user_count').html(msg.user_count);

        // 入室通知
        if (msg.alert) {
            $("#enter").html(user);
            $(".alert").fadeIn();
            setTimeout(() => {
                $(".alert").fadeOut();
            }, 2000);
        }

        // メンバーを全部削除
        let members = $("#members")[0];
        while(members.firstChild){
            members.removeChild(members.firstChild);
        }

        // 最初の人を表示
        $('#members').append('<li class="accordion-header list-group-item list-group-item-light" id="flush-headingOne"></li>')
        $("<button>", {
            type: "button",
            text: msg.members[0],
            class: "accordion-button collapsed list-group-item list-group-item-light",
            "data-bs-toggle": "collapse",
            "data-bs-target": "#flush-collapseOne",
            "aria-expanded": "false",
            "aria-controls": "flush-collapseOne"
        }).appendTo('#flush-headingOne');

        // ルーム内のメンバーの更新
        $('#members').append('<div id="flush-collapseOne" class="accordion-collapse collapse" aria-labelledby="flush-headingOne" data-bs-parent="#accordionFlushExample"></div>')
        for (let i = 1; i < msg.members.length; i++) {
            $("<li>", {
                text: msg.members[i],
                class: "accordion-body list-group-item list-group-item-light"
            }).appendTo('#flush-collapseOne');
        }
    });

    // 名前の表示
    socket.on('display_name', function (msg) {
        let user = msg.name;
        $("#basic-addon3").html(user);
    });

    // ボタンが押されると呼び出される
    $(".message").on("click", function (e) {
        id = $("#id").html();
        let text = $(this).text();
        let user_name = $("#basic-addon3").html();
        socket.emit("chat_message", { text: text , user: user_name , id: id , type: "button"});
    })

     // メッセージが入力されると呼び出される
    $("#form").on("submit", function (e) {
        e.preventDefault();
        id = $("#id").html();
        let text = $("#basic-url").val();
        let user_name = $("#basic-addon3").html();
        if (text) {
            socket.emit("chat_message", { text: text , user: user_name , id: id , type: "message"});
            $("#basic-url").val("")
        }
    })

    // ショートカットキーの設定
    addEventListener("keyup", (e) => {
        let key_code = e.key;
        const button = $(".message");
        if( key_code === "1") button[0].click();
        if( key_code === "2") button[1].click();
        if( key_code === "3") button[2].click();
        if( key_code === "4") button[3].click();
    });

    // メッセージの追加
    socket.on('chat_message', function (msg) {
        // ボタンかチャットの判別
        if (msg.type) {
            $("<li>", { class: "button-msg box" }).prependTo('#messages');
        }
        else {
            $("<li>", { class: "chat-msg box" }).prependTo('#messages');
        }
        // メッセージ表示
        $("<p>", {
            text: msg.text,
            class: "content"
        }).prependTo($(".box")[0]);

        // タイトル表示
        $("<span>", {
            text: "　" + msg.user + " ",
            class: "title"
        }).prependTo($(".box")[0]);

        // 時刻表示
        $("<span>", {
            text: msg.date,
            class: "date"
        }).appendTo($(".title")[0]);
        msg.date

        // アイコン表示
        $("<span>", { class: "icon" }).prependTo($(".title")[0]);

        //連続クリックに対応
        audio.currentTime = 0;
        //クリックしたら音を再生
        audio.play();
    });

    // 音のオンオフの切り替え
    $("#mute").on("click", () => {
        if (audio.muted) {
            audio.muted = false;
            $('#mute').html("mute: OFF");
            $('.mute_btn').css("background", "#668ad8");
        } else {
            audio.muted = true;
            $('#mute').html("mute: ON");
            $('.mute_btn').css("background", "#433947");
        }
    })

    // いいねボタンが押されると呼び出される
    $(".good").on("click", function (msg) {
        id = $("#id").html();
        socket.emit("good_count", { id: id, is_reset: false });
    })

    // いいね数の変更
    socket.on('good_countup', function (msg) {
        $('#good_count').html(msg.good_count);

        $("#good").show();

        // リセット時間の初期化
        $('#good_count').html(msg.good_count);
        if (msg.good_count != 1) {
            clearTimeout(timerID)
        }

        // リセット時間の設定
        timerID = setTimeout(() => {
            socket.emit("good_count", { id: id, is_reset: true });
            $("#good").hide();
        }, resetTime);
    });
});