package {{PACKAGE}};

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.InteractionDialogAPI;
import com.fs.starfarer.api.campaign.rules.MemoryAPI;
import com.fs.starfarer.api.impl.campaign.rulecmd.BaseCommandPlugin;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;

import java.util.List;
import java.util.Map;

/**
 * rules.csv command {{CLASS}}. Its package must be listed in data/config/settings.json:
 *     "ruleCommandPackages": ["{{PACKAGE}}"]
 * The class's simple name is the command, used in a rule's conditions or script column, e.g.
 *     {{CLASS}} status          (condition: true when the condition holds)
 *     {{CLASS}} reward 5000     (script: does something; return value ignored)
 *
 * Memory scopes in memoryMap: MemKeys.LOCAL (the interaction target), MemKeys.GLOBAL, MemKeys.PLAYER,
 * MemKeys.FACTION, MemKeys.MARKET, MemKeys.ENTITY... (rules.csv: $foo = local, $global.foo, $player.foo, ...).
 * If the command adds dialog options, every option id needs a DialogOptionSelected rule with $option == id.
 */
public class {{CLASS}} extends BaseCommandPlugin {
    private static final Logger log = Global.getLogger({{CLASS}}.class);

    @Override
    public boolean execute(String ruleId, InteractionDialogAPI dialog, List<Misc.Token> params,
                           Map<String, MemoryAPI> memoryMap) {
        if (params == null || params.isEmpty()) return false;
        try {
            String action = params.get(0).getString(memoryMap);
            if ("status".equals(action)) {
                return Global.getSector().getMemoryWithoutUpdate().getBoolean("${{PREFIX}}example_flag");
            }
            if ("reward".equals(action) && params.size() > 1) {
                float credits = params.get(1).getFloat(memoryMap);
                Global.getSector().getPlayerFleet().getCargo().getCredits().add(credits);
                if (dialog != null) {
                    dialog.getTextPanel().addPara("Received %s credits.", Misc.getHighlightColor(), Misc.getDGSCredits(credits));
                }
                return true;
            }
            log.warn("{{CLASS}}: unknown action '" + action + "' in rule " + ruleId);
        } catch (Throwable t) {
            log.error("{{CLASS}} failed in rule " + ruleId, t);
        }
        return false;
    }
}
