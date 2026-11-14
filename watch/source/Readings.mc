// Mesures du moment, aux noms de ml/simulation/spec.py (voir WatchReading dans
// backend/schemas.py). Une mesure indisponible n'est pas envoyée : le backend fait sans.
import Toybox.Activity;
import Toybox.ActivityMonitor;
import Toybox.Lang;
import Toybox.SensorHistory;
import Toybox.System;
import Toybox.UserProfile;

module Readings {
    function current() as Dictionary {
        var clock = System.getClockTime();
        var reading = {"local_hour" => clock.hour + clock.min / 60.0};

        var activity = Activity.getActivityInfo();
        if (activity != null) {
            put(reading, "heart_rate", activity.currentHeartRate);
        }

        // Selon le modèle, certains champs n'existent pas (pas d'altimètre = pas d'étages) :
        // chaque champ optionnel est testé avec `has` avant d'être lu.
        var info = ActivityMonitor.getInfo();
        put(reading, "steps_today", info.steps);
        if (info has :floorsClimbed) {
            put(reading, "floors_today", info.floorsClimbed);
        }
        if (info has :activeMinutesDay && info.activeMinutesDay != null) {
            // Comme Garmin : une minute intense compte double.
            var minutes = info.activeMinutesDay;
            put(reading, "intensity_minutes_today", minutes.moderate + 2 * minutes.vigorous);
        }
        if (info has :respirationRate) {
            put(reading, "respiration", info.respirationRate);
        }

        if (Toybox has :SensorHistory) {
            if (SensorHistory has :getStressHistory) {
                put(reading, "stress", latest(SensorHistory.getStressHistory({:period => 1})));
            }
            if (SensorHistory has :getBodyBatteryHistory) {
                put(reading, "body_battery", latest(SensorHistory.getBodyBatteryHistory({:period => 1})));
            }
        }

        var profile = UserProfile.getProfile();
        if (profile has :restingHeartRate) {
            put(reading, "resting_hr", profile.restingHeartRate);
        }
        return reading;
    }

    function latest(history as SensorHistory.SensorHistoryIterator?) {
        if (history == null) {
            return null;
        }
        var sample = history.next();
        return sample == null ? null : sample.data;
    }

    function put(reading as Dictionary, key as String, value) as Void {
        if (value != null) {
            reading[key] = value;
        }
    }
}
