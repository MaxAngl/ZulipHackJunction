// Needed sur la montre : se lier au patient par un code, envoyer les mesures du moment,
// afficher la demande en attente et y répondre depuis le poignet.
import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class NeededApp extends Application.AppBase {
    private var _model as NeededModel;

    function initialize() {
        AppBase.initialize();
        _model = new NeededModel();
    }

    function onStart(state as Dictionary?) as Void {
        _model.start();
    }

    function onStop(state as Dictionary?) as Void {
        _model.stop();
    }

    function getInitialView() {
        return [new NeededView(_model), new NeededDelegate(_model)];
    }
}
