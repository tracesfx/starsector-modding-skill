package tlc.rulecmd;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;
import com.fs.starfarer.api.campaign.CargoAPI;
import com.fs.starfarer.api.campaign.InteractionDialogAPI;
import com.fs.starfarer.api.campaign.RepLevel;
import com.fs.starfarer.api.campaign.TextPanelAPI;
import com.fs.starfarer.api.campaign.rules.MemKeys;
import com.fs.starfarer.api.campaign.rules.MemoryAPI;
import com.fs.starfarer.api.impl.campaign.rulecmd.AddRemoveCommodity;
import com.fs.starfarer.api.impl.campaign.rulecmd.BaseCommandPlugin;
import com.fs.starfarer.api.util.Misc;
import com.fs.starfarer.api.util.Misc.Token;
import org.apache.log4j.Logger;
import tlc.TLCIds;
import tlc.campaign.TLCMem;
import tlc.campaign.TLCQuest;

import java.awt.Color;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * TLCAuditCMD &lt;greet|comply|complyBroke|warrant|exempt|noDomain|refuse|refuseWeak&gt;
 * The Grand Audit: an Assessor fleet hails the player through the vanilla hassle framework.
 */
public class TLCAuditCMD extends BaseCommandPlugin {
    private static final Logger log = Global.getLogger(TLCAuditCMD.class);

    public static final int FEE_PER_SHIP = 250;
    public static final int FEE_MIN = 500;
    public static final int FEE_MAX = 6000;
    public static final int FEE_GAMMA = 500;
    public static final int FEE_BETA = 1000;
    public static final int FEE_ALPHA = 2000;

    /** Repeat-audit asides, chosen at random. */
    private static final String[] REMARKS = {
        "\"For the record, the Bureau notes that your flagship's hull plating does not match any approved pattern. "
            + "This is not a fine. It is a note.\"",
        "\"This circuit has assessed eleven colonies since our last contact. Four of them do not appear in the "
            + "register. Two of the four do not appear on any chart. The Bureau is investigating.\"",
        "\"Please be advised that the Bureau's office hours are continuous.\"",
        "\"The Assessor apologizes for the delay in this audit. It was scheduled two hundred cycles ago.\"",
        "\"Your transponder identifies your fleet by a polity the Bureau does not recognize. It has been entered as "
            + "'other'.\"",
        "\"A previous Assessor on this circuit filed a report describing your fleet as 'courteous'. That report is "
            + "in your file.\"",
        "\"The Bureau reminds all masters of vessels that census participation is mandatory, confidential, and "
            + "deeply appreciated.\"",
        "\"Three vessels on this circuit fired upon the Assessor this month. The Bureau thanks you for not being one "
            + "of them.\"",
    };

    @Override
    public boolean execute(String ruleId, InteractionDialogAPI dialog, List<Token> params, Map<String, MemoryAPI> memoryMap) {
        if (dialog == null || params == null || params.isEmpty()) return false;
        String cmd = params.get(0).getString(memoryMap);
        try {
            if ("greet".equals(cmd)) return greet(dialog, memoryMap);
            if ("comply".equals(cmd)) return comply(dialog, false);
            if ("complyBroke".equals(cmd)) return comply(dialog, true);
            if ("warrant".equals(cmd)) return warrant(dialog);
            if ("exempt".equals(cmd)) return exempt(dialog);
            if ("noDomain".equals(cmd)) return noDomain(dialog);
            if ("refuse".equals(cmd)) return refuse(dialog, true);
            if ("refuseWeak".equals(cmd)) return refuse(dialog, false);
            log.warn("TLC: unknown audit command " + cmd);
        } catch (Throwable t) {
            log.error("TLC: audit command failed: " + cmd, t);
            dialog.getTextPanel().addPara("The Assessor's transmission dissolves into static for a moment, then resumes "
                    + "as though nothing had happened.");
        }
        return false;
    }

    // --------------------------------------------------------------------------------------------- fee
    private static int[] cores() {
        CargoAPI c = Global.getSector().getPlayerFleet().getCargo();
        return new int[]{(int) c.getCommodityQuantity(TLCIds.COMMODITY_GAMMA),
                (int) c.getCommodityQuantity(TLCIds.COMMODITY_BETA),
                (int) c.getCommodityQuantity(TLCIds.COMMODITY_ALPHA)};
    }

    public static int computeFee() {
        CampaignFleetAPI pf = Global.getSector().getPlayerFleet();
        int ships = pf.getFleetData().getNumMembers();
        int base = Math.max(FEE_MIN, Math.min(FEE_MAX, ships * FEE_PER_SHIP));
        int[] c = cores();
        return base + c[0] * FEE_GAMMA + c[1] * FEE_BETA + c[2] * FEE_ALPHA;
    }

    private static String assessorName(InteractionDialogAPI dialog) {
        if (dialog.getInteractionTarget() instanceof CampaignFleetAPI) {
            CampaignFleetAPI f = (CampaignFleetAPI) dialog.getInteractionTarget();
            if (f.getCommander() != null) return f.getCommander().getNameString();
        }
        return "Assessor";
    }

    // --------------------------------------------------------------------------------------------- greet
    private boolean greet(InteractionDialogAPI dialog, Map<String, MemoryAPI> memoryMap) {
        TextPanelAPI t = dialog.getTextPanel();
        Color h = Misc.getHighlightColor();
        Color bad = Misc.getNegativeHighlightColor();
        CampaignFleetAPI pf = Global.getSector().getPlayerFleet();
        CargoAPI cargo = pf.getCargo();
        int fee = computeFee();
        String feeStr = Misc.getDGSCredits(fee);
        MemoryAPI local = memoryMap.get(MemKeys.LOCAL);
        if (local != null) {
            local.set("$tlc_feeStr", feeStr, 0);
            local.set("$tlc_canPay", cargo.getCredits().get() >= fee, 0);
        }
        if (dialog.getInteractionTarget() instanceof CampaignFleetAPI) {
            CampaignFleetAPI f = (CampaignFleetAPI) dialog.getInteractionTarget();
            if (f.getCommander() != null) dialog.getVisualPanel().showPersonInfo(f.getCommander(), true);
        }
        boolean first = TLCMem.getInt(TLCIds.MEM_AUDIT_COUNT) == 0;
        if (first) {
            t.addPara("The comm display resolves into a terminal: a single jade lens behind racks of status readouts, framed "
                    + "in yellowed ivory plating. The voice that follows is calm and unhurried, and it pronounces every word "
                    + "as though it were entering it into a record.");
        }
        t.addPara("\"This is " + assessorName(dialog) + ", Domain Bureau of Colonial Assessment, conducting the Grand "
                + "Audit of the Persean Sector under charter authority.\"");
        if (first) {
            t.addPara("\"Your vessel registrations have lapsed. All of them. The most recent lapse occurred some two "
                    + "hundred cycles ago.\"");
        } else {
            t.addPara("\"Your certificate of assessment is not current. A renewal is required.\"");
            Random r = new Random();
            if (r.nextFloat() < 0.6f) t.addPara(REMARKS[r.nextInt(REMARKS.length)]);
        }
        int ships = pf.getFleetData().getNumMembers();
        t.addPara("\"Please transmit your manifest for assessment. A registration renewal levy of %s applies to your %s.\"",
                h, feeStr, ships == 1 ? "vessel" : ships + " vessels");
        int[] c = cores();
        int n = c[0] + c[1] + c[2];
        if (n > 0) {
            t.addPara("\"Your holds contain %s unlicensed administrative " + (n == 1 ? "intelligence" : "intelligences")
                    + ". Registration at the standard rate is included in the levy.\"", h, "" + n);
        }
        if (cargo.getCommodityQuantity(TLCIds.COMMODITY_DRUGS) + cargo.getCommodityQuantity(TLCIds.COMMODITY_ORGANS) > 0) {
            t.addPara("\"Passive scan has identified prohibited goods in your holds. These will be impounded on "
                    + "assessment.\"", bad, "impounded");
        }
        if (TLCMem.flag(TLCIds.MEM_ENUMERATOR)) {
            t.addPara("A line of text scrolls along the bottom of the display: ENUMERATOR ON RECORD - EXEMPTION AVAILABLE "
                    + "ON REQUEST.", Misc.getGrayColor());
        }
        return true;
    }

    // --------------------------------------------------------------------------------------------- outcomes
    private boolean comply(InteractionDialogAPI dialog, boolean broke) {
        TextPanelAPI t = dialog.getTextPanel();
        Color h = Misc.getHighlightColor();
        CargoAPI cargo = Global.getSector().getPlayerFleet().getCargo();
        int fee = computeFee();
        if (!broke && cargo.getCredits().get() < fee) broke = true;
        if (!broke) {
            cargo.getCredits().subtract(fee);
            AddRemoveCommodity.addCreditsLossText(fee, t);
        }
        for (String id : new String[]{TLCIds.COMMODITY_DRUGS, TLCIds.COMMODITY_ORGANS}) {
            int q = (int) cargo.getCommodityQuantity(id);
            if (q > 0) {
                cargo.removeCommodity(id, q);
                AddRemoveCommodity.addCommodityLossText(id, q, t);
            }
        }
        int[] c = cores();
        if (c[0] + c[1] + c[2] > 0) {
            t.addPara("Registration seals are transmitted to the storage housings of your AI cores. Nothing else happens "
                    + "to them, which is somehow the most unsettling part.");
        }
        String cert = "206-" + (10000 + new Random().nextInt(90000));
        t.addPara("\"Assessment complete. Certificate of Assessment %s has been issued to your fleet, valid for %s days.\"",
                h, cert, broke ? "thirty" : "ninety");
        if (broke) {
            t.addPara("\"Insufficient funds have been noted. A deferred payment schedule has been recorded. The first "
                    + "installment falls due in two hundred and six cycles.\"");
        }
        TLCMem.setFlag(TLCIds.MEM_CERTIFIED, true, broke ? 30f : 90f);
        TLCMem.increment(TLCIds.MEM_AUDIT_COUNT);
        if (!broke) TLCQuest.adjustRep(0.02f, RepLevel.WELCOMING, t);
        if (TLCIds.STAGE_BROADCAST.equals(TLCMem.stage())) {
            t.addPara("\"Your compliance has been noted. Under Emergency Statute 9, the Bureau may engage compliant masters "
                    + "of vessels as provisional enumerators. Should you wish to serve, report to the Registrar of Assize "
                    + "at the Tallyhouse, Assize system.\"", h, "Registrar of Assize", "Assize");
            TLCQuest.setStage(TLCIds.STAGE_REPORT, t);
        }
        t.addPara("\"The Bureau thanks you for your cooperation and wishes you a safe and compliant voyage.\"");
        return true;
    }

    private boolean warrant(InteractionDialogAPI dialog) {
        TextPanelAPI t = dialog.getTextPanel();
        t.addPara("\"Provisional Enumerator's warrant verified. Vessels engaged in Bureau business are exempt from "
                + "assessment under Statute 14(c).\" The lens dims a fraction, which you have come to understand is the "
                + "Bureau's approximation of a nod. \"Thank you for your service, Enumerator.\"");
        TLCMem.setFlag(TLCIds.MEM_CERTIFIED, true, 90f);
        TLCMem.increment(TLCIds.MEM_AUDIT_COUNT);
        TLCQuest.adjustRep(0.01f, RepLevel.WELCOMING, t);
        return true;
    }

    private boolean exempt(InteractionDialogAPI dialog) {
        TextPanelAPI t = dialog.getTextPanel();
        t.addPara("There is a pause of nearly four seconds, which for an administrative intelligence is a very long time.");
        t.addPara("\"Statute 14(c) exemption recorded. Please be advised that misrepresentation of Domain business is an "
                + "offense under Statute 14(d).\" The channel closes before you can ask what the penalty is.");
        TLCMem.setFlag(TLCIds.MEM_CERTIFIED, true, 60f);
        TLCMem.increment(TLCIds.MEM_AUDIT_COUNT);
        return true;
    }

    private boolean noDomain(InteractionDialogAPI dialog) {
        TextPanelAPI t = dialog.getTextPanel();
        int n = TLCMem.increment(TLCIds.MEM_NO_DOMAIN_COUNT);
        String ig = TLCMem.igState();
        if (n == 1) {
            t.addPara("\"That assertion is not supported by the Bureau's records.\" A pause. \"It has been noted.\"");
        } else if (n < TLCIds.NO_DOMAIN_THRESHOLD) {
            t.addPara("\"That assertion has been made to this office before. By you.\" The lens holds perfectly still. "
                    + "\"It is still not supported by the Bureau's records. Your statement has been appended to the "
                    + "earlier one.\"");
        } else if (TLCIds.IG_NONE.equals(ig)) {
            t.addPara("The lens on the display contracts to a pinpoint.");
            t.addPara("\"Three assertions, consistent in substance, from the same master of vessels. Under Statute 2(a), "
                    + "a persistent discrepancy between the record and sworn testimony must be referred to the Office of "
                    + "the Inspector-General.\" A short pause. \"The referral has been filed. The Inspector-General will "
                    + "contact you.\"", Misc.getHighlightColor(), "Inspector-General");
            TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_REFERRED);
        } else if (TLCIds.IG_RULED.equals(ig)) {
            t.addPara("\"The Inspector-General has ruled on that matter.\" The Assessor does not elaborate, and does not "
                    + "seem to want to.");
        } else {
            t.addPara("\"Your assertion has been forwarded to the Inspector-General's docket.\"");
        }
        return true;
    }

    private boolean refuse(InteractionDialogAPI dialog, boolean assessorStronger) {
        TextPanelAPI t = dialog.getTextPanel();
        if (assessorStronger) {
            t.addPara("\"Non-compliance noted. Under Statute 31, the Bureau is authorized to impound the vessels of a "
                    + "non-compliant master pending settlement of the levy.\" The Assessor's tone does not change in the "
                    + "slightest. \"Please do not resist impoundment. Resistance is noted separately.\"");
            TLCQuest.adjustRep(-0.03f, null, t);
        } else {
            t.addPara("\"Non-compliance noted. A notice of deficiency has been filed against your registry.\" The lens "
                    + "lingers on you a moment longer, as if measuring the distance between your fleet and its own. "
                    + "\"You may proceed.\"");
            TLCQuest.adjustRep(-0.02f, null, t);
        }
        return true;
    }
}
