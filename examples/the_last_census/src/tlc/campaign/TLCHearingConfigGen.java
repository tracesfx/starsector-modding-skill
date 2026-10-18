package tlc.campaign;

import com.fs.starfarer.api.impl.campaign.FleetInteractionDialogPluginImpl.FIDConfig;
import com.fs.starfarer.api.impl.campaign.FleetInteractionDialogPluginImpl.FIDConfigGen;

/**
 * Encounter config for the Inspector-General's fleet (stored in its memory, like vanilla's
 * RemnantFleetInteractionConfigGen). The hearing is a duel: nearby stations and other fleets are not pulled in,
 * and the battle has no reputation impact. No fields, so it is trivially save-safe.
 */
public class TLCHearingConfigGen implements FIDConfigGen {
    @Override
    public FIDConfig createConfig() {
        FIDConfig config = new FIDConfig();
        config.pullInStations = false;
        config.pullInAllies = false;
        config.pullInEnemies = false;
        config.impactsEnemyReputation = false;
        config.impactsAllyReputation = false;
        return config;
    }
}
