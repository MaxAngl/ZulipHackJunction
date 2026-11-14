// État de l'app et échanges avec le backend (routes /api/watch/* de backend/main.py).
// Les requêtes passent par l'app Garmin Connect du téléphone, en Bluetooth.
import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.Time;
import Toybox.Timer;
import Toybox.WatchUi;

class NeededModel {
    // Toutes les 5 s : attendre la liaison. Une fois liée : mesures envoyées toutes les 30 s.
    private const TICK_MS = 5000;
    private const SYNC_EVERY_TICKS = 6;

    var token as String? = null; // jeton propre à la montre, gardé entre deux lancements
    var name as String? = null; // prénom du patient
    var pairingCode as String? = null; // les six chiffres à saisir dans l'app web
    var request as Dictionary? = null; // demande en attente : id, text, from_name
    var message as String? = null; // erreur ou confirmation, affichée en bas de l'écran
    var lastSync as Number? = null; // Time.now().value() du dernier envoi réussi

    private var _pairingId as String? = null;
    private var _busy as Boolean = false;
    private var _ticks as Number = 0;
    private var _timer as Timer.Timer;

    function initialize() {
        _timer = new Timer.Timer();
        token = Application.Storage.getValue("token") as String?;
        name = Application.Storage.getValue("name") as String?;
    }

    function start() as Void {
        _timer.start(method(:onTick), TICK_MS, true);
        onTick();
    }

    function stop() as Void {
        _timer.stop();
    }

    function onTick() as Void {
        if (_busy) {
            return;
        }
        if (token == null) {
            if (_pairingId == null) {
                post("/api/watch/pair", {}, method(:onPairing));
            } else {
                get("/api/watch/pair/" + _pairingId, method(:onPairingStatus));
            }
        } else if (_ticks % SYNC_EVERY_TICKS == 0) {
            sync();
        }
        _ticks += 1;
    }

    function sync() as Void {
        post("/api/watch/sync", Readings.current(), method(:onHome));
    }

    // Réponse du patient à la demande affichée : oui, ou pas maintenant.
    function answer(accept as Boolean) as Void {
        if (request == null) {
            return;
        }
        message = accept ? "Sent. Thank you!" : "Okay, maybe later.";
        post("/api/watch/answer", {"request_id" => request["id"], "accept" => accept}, method(:onHome));
    }

    // Oublie la liaison : la montre redemande un code au prochain tic.
    function forget() as Void {
        token = null;
        name = null;
        request = null;
        pairingCode = null;
        _pairingId = null;
        Application.Storage.deleteValue("token");
        Application.Storage.deleteValue("name");
        WatchUi.requestUpdate();
    }

    // --- Réponses du backend -------------------------------------------------------------

    function onPairing(status as Number, data as Dictionary or String or Null) as Void {
        _busy = false;
        if (status == 200 && data instanceof Dictionary) {
            _pairingId = data["pairing_id"] as String;
            pairingCode = data["code"] as String;
            message = null;
        } else {
            message = errorText(status);
        }
        WatchUi.requestUpdate();
    }

    function onPairingStatus(status as Number, data as Dictionary or String or Null) as Void {
        _busy = false;
        if (status == 200 && data instanceof Dictionary) {
            var state = data["status"] as String;
            if (state.equals("linked")) {
                token = data["token"] as String;
                name = data["patient_name"] as String?;
                Application.Storage.setValue("token", token);
                Application.Storage.setValue("name", name);
                _pairingId = null;
                pairingCode = null;
                _ticks = 0;
            } else if (state.equals("expired")) {
                _pairingId = null; // nouveau code au prochain tic
                pairingCode = null;
            }
        } else if (status == 404) {
            _pairingId = null;
        } else {
            message = errorText(status);
        }
        WatchUi.requestUpdate();
    }

    function onHome(status as Number, data as Dictionary or String or Null) as Void {
        _busy = false;
        if (status == 200 && data instanceof Dictionary) {
            name = data["name"] as String;
            request = data["request"] as Dictionary?;
            lastSync = Time.now().value();
            if (request != null) {
                message = null;
            }
        } else if (status == 401) {
            forget(); // déliée depuis l'app web
        } else {
            message = errorText(status);
        }
        WatchUi.requestUpdate();
    }

    // --- Intérieur -----------------------------------------------------------------------

    private function serverUrl() as String {
        var url = Application.Properties.getValue("ServerUrl") as String?;
        return (url == null || url.length() == 0) ? "http://localhost:8000" : url;
    }

    private function options(method as Communications.HttpRequestMethod) as Dictionary {
        var headers = {"Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON};
        if (token != null) {
            headers["X-Needed-Token"] = token;
        }
        return {
            :method => method,
            :headers => headers,
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
    }

    private function post(path as String, body as Dictionary, callback as Method) as Void {
        _busy = true;
        Communications.makeWebRequest(
            serverUrl() + path, body, options(Communications.HTTP_REQUEST_METHOD_POST), callback
        );
    }

    private function get(path as String, callback as Method) as Void {
        _busy = true;
        Communications.makeWebRequest(
            serverUrl() + path, null, options(Communications.HTTP_REQUEST_METHOD_GET), callback
        );
    }

    private function errorText(status as Number) as String {
        if (status == Communications.BLE_CONNECTION_UNAVAILABLE) {
            return "Phone not connected";
        }
        if (status == Communications.SECURE_CONNECTION_REQUIRED) {
            return "Server needs HTTPS";
        }
        if (status == Communications.NETWORK_REQUEST_TIMED_OUT) {
            return "Server not responding";
        }
        return "Error " + status;
    }
}
