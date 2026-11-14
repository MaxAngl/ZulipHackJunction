// Un seul écran, selon l'état : code de liaison, demande en attente, ou rien à faire.
// Charte de l'app : noir, blanc, un seul accent cyan.
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Time;
import Toybox.WatchUi;

class NeededView extends WatchUi.View {
    private const ACCENT = 0x00D8FF;
    private var _model as NeededModel;

    function initialize(model as NeededModel) {
        View.initialize();
        _model = model;
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        var width = dc.getWidth();
        var height = dc.getHeight();
        var cx = width / 2;
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();

        dc.setColor(ACCENT, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, height * 0.1, Graphics.FONT_XTINY, "NEEDED", Graphics.TEXT_JUSTIFY_CENTER);

        if (_model.token == null) {
            drawPairing(dc, cx, height);
        } else if (_model.request != null) {
            drawRequest(dc, cx, width, height);
        } else {
            drawIdle(dc, cx, height);
        }

        if (_model.message != null) {
            dc.setColor(ACCENT, Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, height * 0.8, Graphics.FONT_XTINY, _model.message, Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    private function drawPairing(dc as Graphics.Dc, cx as Number, height as Number) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        if (_model.pairingCode == null) {
            dc.drawText(cx, height * 0.42, Graphics.FONT_SMALL, "Getting a code…", Graphics.TEXT_JUSTIFY_CENTER);
            return;
        }
        dc.drawText(cx, height * 0.25, Graphics.FONT_XTINY, "Enter this code\nin the Needed app", Graphics.TEXT_JUSTIFY_CENTER);
        dc.setColor(ACCENT, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, height * 0.45, Graphics.FONT_NUMBER_MEDIUM, _model.pairingCode, Graphics.TEXT_JUSTIFY_CENTER);
    }

    private function drawRequest(dc as Graphics.Dc, cx as Number, width as Number, height as Number) as Void {
        var request = _model.request as Dictionary;
        dc.setColor(ACCENT, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, height * 0.2, Graphics.FONT_XTINY, request["from_name"] + " is asking you", Graphics.TEXT_JUSTIFY_CENTER);
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        var text = Graphics.fitTextToArea(request["text"] as String, Graphics.FONT_XTINY, width * 0.78, height * 0.4, true);
        dc.drawText(cx, height * 0.3, Graphics.FONT_XTINY, text, Graphics.TEXT_JUSTIFY_CENTER);
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, height * 0.72, Graphics.FONT_XTINY, "Press START to answer", Graphics.TEXT_JUSTIFY_CENTER);
    }

    private function drawIdle(dc as Graphics.Dc, cx as Number, height as Number) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        var greeting = _model.name == null ? "Hello" : "Hello " + _model.name;
        dc.drawText(cx, height * 0.3, Graphics.FONT_SMALL, greeting, Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(cx, height * 0.45, Graphics.FONT_XTINY, "Nothing for now.", Graphics.TEXT_JUSTIFY_CENTER);
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, height * 0.6, Graphics.FONT_XTINY, syncText(), Graphics.TEXT_JUSTIFY_CENTER);
    }

    private function syncText() as String {
        if (_model.lastSync == null) {
            return "Connecting…";
        }
        var seconds = Time.now().value() - _model.lastSync;
        return seconds < 60 ? "Data sent just now" : "Data sent " + (seconds / 60) + " min ago";
    }
}
