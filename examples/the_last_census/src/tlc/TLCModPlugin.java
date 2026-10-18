package tlc;

import com.fs.starfarer.api.BaseModPlugin;
import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.SectorAPI;
import com.thoughtworks.xstream.XStream;
import org.apache.log4j.Logger;
import tlc.campaign.TLCAssessorManager;
import tlc.campaign.TLCAutomatedAdminCondition;
import tlc.campaign.TLCCensusIntel;
import tlc.campaign.TLCFleetListener;
import tlc.campaign.TLCHearingConfigGen;
import tlc.campaign.TLCHearingIntel;
import tlc.compat.TLCGraphicsLibCompat;
import tlc.world.TLCWorldGen;

public class TLCModPlugin extends BaseModPlugin {
    private static final Logger log = Global.getLogger(TLCModPlugin.class);

    @Override
    public void onApplicationLoad() throws Exception {
        log.info("The Last Census loaded. The Grand Audit is pending.");
        // Optional: dynamic lights for Bureau projectiles when GraphicsLib is present.
        if (Global.getSettings().getModManager().isModEnabled("shaderLib")) {
            try {
                TLCGraphicsLibCompat.loadLights();
            } catch (Throwable t) {
                log.warn("TLC: GraphicsLib is enabled but light data could not be loaded", t);
            }
        }
    }

    @Override
    public void onNewGame() {
        try {
            TLCWorldGen.generateIfNeeded(Global.getSector());
        } catch (Throwable t) {
            log.error("TLC: world generation failed in onNewGame", t);
        }
    }

    @Override
    public void onGameLoad(boolean newGame) {
        SectorAPI sector = Global.getSector();
        if (sector == null) return;
        try {
            // Existing saves receive the content once; the call is idempotent (guarded by a sector memory flag).
            if (!newGame) TLCWorldGen.generateIfNeeded(sector);
            TLCWorldGen.ensurePeople(sector);
            if (!sector.hasScript(TLCAssessorManager.class)) {
                sector.addScript(new TLCAssessorManager());
            }
        } catch (Throwable t) {
            log.error("TLC: onGameLoad setup failed", t);
        }
    }

    @Override
    public void configureXStream(XStream x) {
        x.alias("TLC_AssessorManager", TLCAssessorManager.class);
        x.alias("TLC_CensusIntel", TLCCensusIntel.class);
        x.alias("TLC_HearingIntel", TLCHearingIntel.class);
        x.alias("TLC_FleetListener", TLCFleetListener.class);
        x.alias("TLC_HearingConfigGen", TLCHearingConfigGen.class);
        x.alias("TLC_AutomatedAdmin", TLCAutomatedAdminCondition.class);
    }
}
