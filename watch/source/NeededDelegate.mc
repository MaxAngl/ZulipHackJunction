// Boutons : START répond à la demande affichée ; MENU (appui long sur UP) permet de relier
// la montre à un autre compte.
import Toybox.Lang;
import Toybox.WatchUi;

class NeededDelegate extends WatchUi.BehaviorDelegate {
    private var _model as NeededModel;

    function initialize(model as NeededModel) {
        BehaviorDelegate.initialize();
        _model = model;
    }

    function onSelect() as Boolean {
        if (_model.request == null) {
            return false;
        }
        var menu = new WatchUi.Menu2({:title => "Your answer"});
        menu.addItem(new WatchUi.MenuItem("Yes, I'll help", null, :yes, {}));
        menu.addItem(new WatchUi.MenuItem("Not now", null, :no, {}));
        WatchUi.pushView(menu, new AnswerDelegate(_model), WatchUi.SLIDE_UP);
        return true;
    }

    function onMenu() as Boolean {
        if (_model.token == null) {
            return false;
        }
        var menu = new WatchUi.Menu2({:title => "Needed"});
        menu.addItem(new WatchUi.MenuItem("Link again", "New code", :forget, {}));
        WatchUi.pushView(menu, new SettingsDelegate(_model), WatchUi.SLIDE_UP);
        return true;
    }
}

class AnswerDelegate extends WatchUi.Menu2InputDelegate {
    private var _model as NeededModel;

    function initialize(model as NeededModel) {
        Menu2InputDelegate.initialize();
        _model = model;
    }

    function onSelect(item as WatchUi.MenuItem) as Void {
        _model.answer(item.getId() == :yes);
        WatchUi.popView(WatchUi.SLIDE_DOWN);
    }
}

class SettingsDelegate extends WatchUi.Menu2InputDelegate {
    private var _model as NeededModel;

    function initialize(model as NeededModel) {
        Menu2InputDelegate.initialize();
        _model = model;
    }

    function onSelect(item as WatchUi.MenuItem) as Void {
        _model.forget();
        WatchUi.popView(WatchUi.SLIDE_DOWN);
    }
}
