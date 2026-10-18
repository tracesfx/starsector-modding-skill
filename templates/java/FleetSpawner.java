package {{PACKAGE}};

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;
import com.fs.starfarer.api.campaign.FleetAssignment;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.rules.MemoryAPI;
import com.fs.starfarer.api.impl.campaign.fleets.FleetFactoryV3;
import com.fs.starfarer.api.impl.campaign.fleets.FleetParamsV3;
import com.fs.starfarer.api.impl.campaign.ids.FleetTypes;
import com.fs.starfarer.api.impl.campaign.ids.MemFlags;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;

/**
 * Spawns a "{{NAME}}" fleet with the vanilla fleet factory.
 *
 * Rules learned the hard way: (1) createFleet can return null (no valid ships for the faction/points) - always check;
 * (2) before setting any MemFlags flag, run `api_lookup.py uses <FLAG>` and copy what vanilla does - flags such as
 * MEMORY_KEY_NO_JUMP or FLEET_IGNORES_OTHER_FLEETS have side effects (stranding the fleet, ignoring the player);
 * (3) set flags with Misc.setFlagWithReason so they can be cleared by reason, and give every flag a removal point;
 * (4) end with a despawn assignment so the fleet does not live forever.
 */
public final class {{CLASS}} {
    private static final Logger log = Global.getLogger({{CLASS}}.class);
    public static final String FLAG_REASON = "{{PREFIX}}{{CLASS}}";

    private {{CLASS}}() {
    }

    public static CampaignFleetAPI spawn(String factionId, SectorEntityToken near, float combatPoints, boolean hostileToPlayer) {
        if (near == null || near.getContainingLocation() == null || Global.getSector().getFaction(factionId) == null) return null;
        FleetParamsV3 params = new FleetParamsV3(
                near.getMarket(),                 // source market (may be null)
                near.getLocationInHyperspace(),   // location in hyperspace
                factionId,
                null,                             // quality override (null = from the source market)
                FleetTypes.PATROL_MEDIUM,
                combatPoints,                     // combat points
                0f, 0f, 0f, 0f, 0f,               // freighter, tanker, transport, liner, utility points
                0f);                              // quality mod
        CampaignFleetAPI fleet = FleetFactoryV3.createFleet(params);
        if (fleet == null || fleet.isEmpty()) {
            log.warn("{{CLASS}}: no fleet for faction " + factionId + " at " + combatPoints + " points");
            return null;
        }
        near.getContainingLocation().addEntity(fleet);
        fleet.setLocation(near.getLocation().x, near.getLocation().y);
        MemoryAPI mem = fleet.getMemoryWithoutUpdate();
        if (hostileToPlayer) {
            Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_HOSTILE, FLAG_REASON, true, 30f);
            Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_AGGRESSIVE, FLAG_REASON, true, 30f);
        }
        fleet.addAssignment(FleetAssignment.PATROL_SYSTEM, near, 20f);
        fleet.addAssignment(FleetAssignment.GO_TO_LOCATION_AND_DESPAWN, near, 30f);
        return fleet;
    }
}
