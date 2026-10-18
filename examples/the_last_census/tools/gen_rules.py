"""
gen_rules.py - writes data/campaign/rules.csv for The Last Census.
Each rule: (id, trigger, conditions[], script[], text, options[]).  Run from the mod root.

Patterns mirror vanilla exactly:
  * audits use the vanilla hassle framework (BeginFleetEncounter + $pursuePlayer_hassle + HailPlayer + OpenCommLink),
    modelled on the Knights of Ludd "sacredProtectors" tithe rules;
  * option menus are rebuilt with FireAll <trigger> (FireAll clears and re-adds options);
  * market menu options use PopulateOptions + $menuState == main, and return with FireAll PopulateOptions.
"""
import csv
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = ["id", "trigger", "conditions", "script", "text", "options", "notes"]
R = []


def rule(rid, trigger, cond=(), script=(), text="", options=(), notes=""):
    R.append([rid, trigger, "\n".join(cond), "\n".join(script), text, "\n".join(options), notes])


# ============================================================================ THE GRAND AUDIT
rule("tlc_auditBegin", "BeginFleetEncounter",
     ["!$hassle_didAlready", "!$isHostile", "$pursuePlayer_hassle score:50", "$hassleType == tlc_audit",
      "!$global.tlc_certified", "!$global.tlc_commissioner", "!$global.tlc_auditsEnded"],
     ["$hassle_didAlready = true 0", "$hassleComplete = true", "MakeOtherFleetPreventDisengage hassle true",
      "unset $ignorePlayerCommRequests", "$tlc_auditConv = true 0", "HailPlayer"],
     notes="Assessor fleet hails the player (vanilla hassle framework)")
rule("tlc_auditComms", "OpenCommLink",
     ["$entity.tlc_auditConv score:100"],
     ["$entity.ignorePlayerCommRequests = true 7", "TLCAuditCMD greet", "FireAll TLC_AuditOptions"])
rule("tlc_auditOptComply", "TLC_AuditOptions", ["$tlc_canPay"], [], "",
     ["1:tlc_auditComply:Transmit the manifest and pay the $tlc_feeStr levy"])
rule("tlc_auditOptBroke", "TLC_AuditOptions", ["!$tlc_canPay"], [], "",
     ["1:tlc_auditComplyBroke:Transmit the manifest and explain that you cannot pay $tlc_feeStr"])
rule("tlc_auditOptWarrant", "TLC_AuditOptions", ["$global.tlc_enumerator"], [], "",
     ["2:tlc_auditWarrant:Present your Provisional Enumerator's warrant"])
rule("tlc_auditOptExempt", "TLC_AuditOptions", ["!$global.tlc_enumerator"],
     ['SetStoryOption tlc_auditExempt general "Talked your way out of a Bureau audit"'], "",
     ['3:tlc_auditExempt:"This vessel is engaged in Domain business. Statute 14(c)." (lie)'])
rule("tlc_auditOptNoDomain", "TLC_AuditOptions", ["!$tlc_saidNoDomain"], [], "",
     ['4:tlc_auditNoDomain:"There is no Domain."'])
rule("tlc_auditOptRefuse", "TLC_AuditOptions", [], [], "", ["5:tlc_auditRefuse:Refuse the audit"])

rule("tlc_auditComplySel", "DialogOptionSelected", ["$option == tlc_auditComply"],
     ["TLCAuditCMD comply", "MakeOtherFleetPreventDisengage hassle false"], "", ["cutCommLinkNoText:Cut the comm link"])
rule("tlc_auditBrokeSel", "DialogOptionSelected", ["$option == tlc_auditComplyBroke"],
     ["TLCAuditCMD complyBroke", "MakeOtherFleetPreventDisengage hassle false"], "",
     ["cutCommLinkNoText:Cut the comm link"])
rule("tlc_auditWarrantSel", "DialogOptionSelected", ["$option == tlc_auditWarrant"],
     ["TLCAuditCMD warrant", "MakeOtherFleetPreventDisengage hassle false"], "", ["cutCommLinkNoText:Cut the comm link"])
rule("tlc_auditExemptSel", "DialogOptionSelected", ["$option == tlc_auditExempt"],
     ["TLCAuditCMD exempt", "MakeOtherFleetPreventDisengage hassle false"], "", ["cutCommLinkNoText:Cut the comm link"])
rule("tlc_auditNoDomainSel", "DialogOptionSelected", ["$option == tlc_auditNoDomain"],
     ["$tlc_saidNoDomain = true 0", "TLCAuditCMD noDomain", "FireAll TLC_AuditOptions"],
     notes="three separate audits -> Inspector-General referral (secret)")
rule("tlc_auditRefuseStrongSel", "DialogOptionSelected", ["$option == tlc_auditRefuse", "$entity.relativeStrength >= 0"],
     ["TLCAuditCMD refuse", "MakeOtherFleetLowRepImpact tlc_audit true", "MakeOtherFleetHostile hassle true",
      "MakeOtherFleetAggressive hassle true"], "",
     ["cutCommLinkNoText:Cut the comm link and prepare to resist impoundment"])
rule("tlc_auditRefuseWeakSel", "DialogOptionSelected", ["$option == tlc_auditRefuse", "$entity.relativeStrength < 0"],
     ["TLCAuditCMD refuseWeak", "MakeOtherFleetPreventDisengage hassle false"], "",
     ["cutCommLinkNoText:Cut the comm link"])

# ============================================================================ THE REGISTRAR (Tallyhouse)
rule("tlc_regOpt", "PopulateOptions",
     ["$hasMarket", "$menuState == main", "$market.id == tlc_tallyhouse_market", "!$faction.isHostile"], [], "",
     ["3:tlc_registrarOpen:Request an audience with the Registrar"])
rule("tlc_regOpenSel", "DialogOptionSelected", ["$option == tlc_registrarOpen"],
     ["TLCRegistrarCMD show", "FireAll TLC_RegistrarOptions"])

rule("tlc_regOptAskAudit", "TLC_RegistrarOptions", ["!$global.tlc_askedAudit"], [], "",
     ['1:tlc_regAskAudit:"What is the Grand Audit?"'])
rule("tlc_regOptWarrant", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn broadcast report"], [], "",
     ['2:tlc_regAcceptWarrant:"I will serve as an enumerator."'])
rule("tlc_regOptReturnsStatus", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn returns", "TLCCensusCMD returnsPending"],
     [], "", ['2:tlc_regReturnsStatus:"About the census returns..."'])
rule("tlc_regOptSubmit", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn returns", "TLCCensusCMD returnsDone"], [], "",
     ['1:tlc_regSubmitReturns:"I have filed the returns you asked for."'])
rule("tlc_regOptRelayStatus", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn relay", "!$global.tlc_relayActive"], [], "",
     ['1:tlc_regRelayStatus:"About the courier relay..."'])
rule("tlc_regOptTransmit", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn relay", "$global.tlc_relayActive"], [], "",
     ['1:tlc_regTransmit:"The relay at Envoi is online."'])
rule("tlc_regOptLetter", "TLC_RegistrarOptions", ["$global.tlc_hasLetter", "!$global.tlc_letterDelivered"], [], "",
     ["3:tlc_regGiveLetter:Give the Registrar the sealed letter from the Dead Letter Office"])
rule("tlc_regOptAskDomain", "TLC_RegistrarOptions", [], [], "",
     ['4:tlc_regAskDomain:"Do you know what happened to the Domain?"'])
rule("tlc_regOptAfter", "TLC_RegistrarOptions", ["TLCCensusCMD stageIn done"], [], "",
     ['1:tlc_regAfter:"How is the Bureau?"'])
rule("tlc_regOptLeave", "TLC_RegistrarOptions", [], [], "", ["99:tlc_regLeave:End the audience"])

rule("tlc_regAskAuditSel", "DialogOptionSelected", ["$option == tlc_regAskAudit"],
     ["$global.tlc_askedAudit = true", "TLCRegistrarCMD askAudit", "FireAll TLC_RegistrarOptions"])
rule("tlc_regAcceptWarrantSel", "DialogOptionSelected", ["$option == tlc_regAcceptWarrant"],
     ["TLCRegistrarCMD acceptWarrant", "FireAll TLC_RegistrarOptions"])
rule("tlc_regReturnsStatusSel", "DialogOptionSelected", ["$option == tlc_regReturnsStatus"],
     ["TLCRegistrarCMD returnsStatus", "FireAll TLC_RegistrarOptions"])
rule("tlc_regSubmitReturnsSel", "DialogOptionSelected", ["$option == tlc_regSubmitReturns"],
     ["TLCRegistrarCMD submitReturns", "FireAll TLC_RegistrarOptions"])
rule("tlc_regRelayStatusSel", "DialogOptionSelected", ["$option == tlc_regRelayStatus"],
     ["TLCRegistrarCMD relayStatus", "FireAll TLC_RegistrarOptions"])
rule("tlc_regTransmitSel", "DialogOptionSelected", ["$option == tlc_regTransmit"],
     ["TLCRegistrarCMD transmit", "FireAll TLC_FinalOptions"])
rule("tlc_regGiveLetterSel", "DialogOptionSelected", ["$option == tlc_regGiveLetter"],
     ["TLCRegistrarCMD giveLetter", "FireAll TLC_RegistrarOptions"])
rule("tlc_regAskDomainSel", "DialogOptionSelected", ["$option == tlc_regAskDomain"],
     ["TLCRegistrarCMD askDomain", "FireAll TLC_RegistrarOptions"])
rule("tlc_regAfterSel", "DialogOptionSelected", ["$option == tlc_regAfter"],
     ["TLCRegistrarCMD after", "FireAll TLC_RegistrarOptions"])
rule("tlc_regLeaveSel", "DialogOptionSelected", ["$option == tlc_regLeave"],
     ["ShowDefaultVisual", "FireAll PopulateOptions"], "You take your leave of the Registrar.")

rule("tlc_finOptNoDomain", "TLC_FinalOptions", [], [], "", ['1:tlc_endNoDomain:"No. The Domain is gone."'])
rule("tlc_finOptKeepCounting", "TLC_FinalOptions", [], [], "",
     ['2:tlc_endKeepCounting:"Someone will be. Keep counting."'])
rule("tlc_finOptRuled", "TLC_FinalOptions", ["$global.tlc_igState == ruled"], [], "",
     ['0:tlc_endRuled:"Your Inspector-General already ruled on that."'])
rule("tlc_endNoDomainSel", "DialogOptionSelected", ["$option == tlc_endNoDomain"], ["TLCRegistrarCMD endArchived"], "",
     ["tlc_regLeave:Leave the audience chamber"])
rule("tlc_endKeepCountingSel", "DialogOptionSelected", ["$option == tlc_endKeepCounting"],
     ["TLCRegistrarCMD endContinuing"], "", ["tlc_regLeave:Leave the audience chamber"])
rule("tlc_endRuledSel", "DialogOptionSelected", ["$option == tlc_endRuled"], ["TLCRegistrarCMD endRuled"], "",
     ["tlc_regLeave:Leave the audience chamber"])

# ============================================================================ CENSUS RETURNS (any eligible market)
rule("tlc_censusOpt", "PopulateOptions",
     ["$hasMarket", "$menuState == main", "$global.tlc_enumerator", "TLCCensusCMD canFile"], [], "",
     ["4:tlc_censusFile:File a Bureau census return for this colony"])
rule("tlc_censusFileSel", "DialogOptionSelected", ["$option == tlc_censusFile"],
     ["TLCCensusCMD fileReturn", "FireAll PopulateOptions"])

# ============================================================================ THE COURIER RELAY (Envoi)
rule("tlc_relayOpen", "OpenInteractionDialog", ["$customType == tlc_courier_relay score:1000"],
     ["ShowDefaultVisual", "TLCCensusCMD relayEnter", "FireAll TLC_RelayOptions"])
rule("tlc_relayOptActivate", "TLC_RelayOptions",
     ["TLCCensusCMD stageIn relay", "!$global.tlc_relayActive", "TLCCensusCMD relayClear"], [], "",
     ["1:tlc_relayActivate:Install the Registrar's transmission key"])
rule("tlc_relayOptLeave", "TLC_RelayOptions", [], [], "", ["99:tlc_relayLeave:Leave"])
rule("tlc_relayActivateSel", "DialogOptionSelected", ["$option == tlc_relayActivate"], ["TLCCensusCMD activateRelay"],
     "", ["tlc_relayLeave:Leave"])
rule("tlc_relayLeaveSel", "DialogOptionSelected", ["$option == tlc_relayLeave"], ["DismissDialog"])

# ============================================================================ THE DEAD LETTER OFFICE (secret)
rule("tlc_dloOpen", "OpenInteractionDialog", ["$customType == tlc_dead_letter_office score:1000"],
     ["ShowDefaultVisual", "TLCCensusCMD dloEnter", "FireAll TLC_DLOOptions"])
rule("tlc_dloOptRead", "TLC_DLOOptions", [], [], "", ["1:tlc_dloRead:Read an undelivered letter"])
rule("tlc_dloOptSearch", "TLC_DLOOptions", ["!$global.tlc_dloSearched"], [], "",
     ["2:tlc_dloSearch:Search the rest of the annex"])
rule("tlc_dloOptLeave", "TLC_DLOOptions", [], [], "", ["99:tlc_dloLeave:Leave"])
rule("tlc_dloReadSel", "DialogOptionSelected", ["$option == tlc_dloRead"],
     ["TLCCensusCMD dloRead", "FireAll TLC_DLOOptions"])
rule("tlc_dloSearchSel", "DialogOptionSelected", ["$option == tlc_dloSearch"],
     ["$global.tlc_dloSearched = true", "TLCCensusCMD dloSearch", "FireAll TLC_DLOOptions"])
rule("tlc_dloLeaveSel", "DialogOptionSelected", ["$option == tlc_dloLeave"], ["DismissDialog"])

# ============================================================================ THE HEARING (secret)
rule("tlc_igBegin", "BeginFleetEncounter", ["$tlc_igFleet score:200", "!$isHostile", "TLCHearingCMD active"],
     ["$tlc_igConv = true 0", "unset $ignorePlayerCommRequests", "MakeOtherFleetPreventDisengage tlc_hearing true",
      "HailPlayer"],
     notes="Inspector-General hails the player")
rule("tlc_igComms", "OpenCommLink", ["$entity.tlc_igConv score:200"],
     ["TLCHearingCMD greet", "FireAll TLC_HearingOptions"])
rule("tlc_igOptSubmit", "TLC_HearingOptions", [], [], "", ['1:tlc_igSubmit:"Proceed."'])
rule("tlc_igOptDefer", "TLC_HearingOptions", [], [], "", ['2:tlc_igDefer:"Not today."'])
rule("tlc_igSubmitSel", "DialogOptionSelected", ["$option == tlc_igSubmit"],
     ["TLCHearingCMD submit", "MakeOtherFleetNoRepImpact tlc_hearing true", "MakeOtherFleetHostile tlc_hearing true",
      "MakeOtherFleetAggressive tlc_hearing true"], "",
     ["cutCommLinkNoText:Cut the comm link and prepare for the hearing"])
rule("tlc_igDeferSel", "DialogOptionSelected", ["$option == tlc_igDefer"],
     ["TLCHearingCMD defer", "MakeOtherFleetPreventDisengage tlc_hearing false"], "",
     ["cutCommLinkNoText:Cut the comm link"])

if __name__ == "__main__":
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(HEADER)
    for r in R:
        w.writerow(r)
    p = os.path.join(ROOT, "data", "campaign", "rules.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(out.getvalue())
    print("wrote data/campaign/rules.csv", len(R), "rules")
