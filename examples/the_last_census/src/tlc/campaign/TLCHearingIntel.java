package tlc.campaign;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;
import com.fs.starfarer.api.campaign.FactionAPI;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.comm.IntelInfoPlugin;
import com.fs.starfarer.api.impl.campaign.ids.Tags;
import com.fs.starfarer.api.impl.campaign.intel.BaseIntelPlugin;
import com.fs.starfarer.api.ui.SectorMapAPI;
import com.fs.starfarer.api.ui.TooltipMakerAPI;
import com.fs.starfarer.api.util.Misc;
import tlc.TLCIds;

import java.awt.Color;
import java.util.Set;

/** Intel for the secret Inspector-General hearing. State lives in global memory (TLCIds.MEM_IG_STATE). */
public class TLCHearingIntel extends BaseIntelPlugin {

    private CampaignFleetAPI fleet;

    public TLCHearingIntel(CampaignFleetAPI fleet) {
        this.fleet = fleet;
    }

    public static TLCHearingIntel get() {
        IntelInfoPlugin p = Global.getSector().getIntelManager().getFirstIntel(TLCHearingIntel.class);
        return p instanceof TLCHearingIntel ? (TLCHearingIntel) p : null;
    }

    public void setFleet(CampaignFleetAPI fleet) {
        this.fleet = fleet;
    }

    public CampaignFleetAPI getFleetRef() {
        return fleet;
    }

    @Override
    protected String getName() {
        if (TLCIds.IG_RULED.equals(TLCMem.igState())) return "Office of the Inspector-General - Finding Filed";
        return "Office of the Inspector-General";
    }

    @Override
    public String getIcon() {
        return Global.getSettings().getSpriteName("intel", "tlc_inspector");
    }

    @Override
    public Set<String> getIntelTags(SectorMapAPI map) {
        Set<String> tags = super.getIntelTags(map);
        tags.add(Tags.INTEL_STORY);
        tags.add(TLCIds.FACTION_BUREAU);
        return tags;
    }

    @Override
    public FactionAPI getFactionForUIColors() {
        FactionAPI f = TLCMem.bureau();
        return f != null ? f : super.getFactionForUIColors();
    }

    @Override
    public SectorEntityToken getMapLocation(SectorMapAPI map) {
        String s = TLCMem.igState();
        if (TLCIds.IG_DISPATCHED.equals(s) && fleet != null && fleet.isAlive() && fleet.isVisibleToPlayerFleet()) {
            return fleet;
        }
        if (TLCIds.IG_WAITING.equals(s) && fleet != null && fleet.isAlive()) return fleet; // she told you where
        return TLCMem.tallyhouse();
    }

    @Override
    protected void addBulletPoints(TooltipMakerAPI info, ListInfoMode mode, boolean isUpdate, Color tc, float initPad) {
        Color h = Misc.getHighlightColor();
        String s = TLCMem.igState();
        if (TLCIds.IG_DISPATCHED.equals(s)) {
            info.addPara("The Inspector-General is coming to hear your testimony", initPad, tc, h, "Inspector-General");
        } else if (TLCIds.IG_WAITING.equals(s)) {
            info.addPara("The Inspector-General holds session at Docket, in Assize", initPad, tc, h, "Docket");
        } else if (TLCIds.IG_RULED.equals(s)) {
            info.addPara("Finding: Domain contact presumed lost", initPad, tc, h, "presumed lost");
        } else {
            info.addPara("A referral is pending", initPad, tc);
        }
    }

    @Override
    public void createSmallDescription(TooltipMakerAPI info, float width, float height) {
        float opad = 10f;
        Color h = Misc.getHighlightColor();
        info.addPara("Three Bureau Assessors recorded the same testimony from you: that the Domain no longer exists. "
                + "Under the Bureau's statutes, a persistent discrepancy between the record and sworn testimony must be "
                + "referred to the Office of the Inspector-General.", opad);
        String s = TLCMem.igState();
        if (TLCIds.IG_DISPATCHED.equals(s) || TLCIds.IG_REFERRED.equals(s)) {
            info.addPara("The Inspector-General's flagship has been dispatched to hear the matter in person.", opad);
        } else if (TLCIds.IG_WAITING.equals(s)) {
            info.addPara("The hearing is adjourned. The Inspector-General is holding session in orbit of %s, in the Assize "
                    + "system, and will hear your evidence when you present yourself.", opad, h, "Docket");
        } else if (TLCIds.IG_RULED.equals(s)) {
            info.addPara("The hearing is over. The Inspector-General tested the hypothesis in the only way it trusted, "
                    + "and you supplied the evidence. The finding, filed with the Registrar of Assize, reads: %s",
                    opad, h, "Domain contact presumed lost.");
        }
    }

    @Override
    public String getSortString() {
        return "Office of the Inspector-General";
    }

    @Override
    public IntelSortTier getSortTier() {
        return TLCIds.IG_RULED.equals(TLCMem.igState()) ? IntelSortTier.TIER_COMPLETED : super.getSortTier();
    }

    @Override
    public boolean shouldRemoveIntel() {
        return false;
    }
}
