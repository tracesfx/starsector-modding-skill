package {{PACKAGE}};

import com.fs.starfarer.api.EveryFrameScript;
import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.util.IntervalUtil;
import org.apache.log4j.Logger;

/**
 * Campaign script "{{NAME}}". Add it once, e.g. from ModPlugin.onGameLoad:
 *     if (!Global.getSector().hasScript({{CLASS}}.class)) Global.getSector().addScript(new {{CLASS}}());
 * Scripts added with addScript are saved with the game (keep fields serializable); use addTransientScript for
 * scripts that should not be saved, and re-add those on every load.
 * One in-game day is 10 seconds of campaign time (wiki); Global.getSector().getClock() gives days elapsed.
 */
public class {{CLASS}} implements EveryFrameScript {
    private static final Logger log = Global.getLogger({{CLASS}}.class);
    private final IntervalUtil interval = new IntervalUtil(1f, 1f); // check once per in-game tenth of a day
    private boolean done = false;

    @Override
    public void advance(float amount) {
        if (done || Global.getSector() == null || Global.getSector().isPaused()) return;
        float days = Global.getSector().getClock().convertToDays(amount);
        interval.advance(days);
        if (!interval.intervalElapsed()) return;
        try {
            // periodic campaign logic; re-check every condition here, not when the work was scheduled
        } catch (Throwable t) {
            log.error("{{CLASS}} failed; stopping it", t);
            done = true;
        }
    }

    @Override
    public boolean isDone() {
        return done;
    }

    @Override
    public boolean runWhilePaused() {
        return false;
    }
}
