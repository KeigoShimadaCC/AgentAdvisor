import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ALTITUDES, useAltitude } from "../shell/altitude";
import { getPresence, setPresence, type Presence } from "../shell/presence";
import { permissionState, requestPermissionOnRun } from "../../presence/notify";
import { readDraft, writeDraft } from "../NewDecision/commissionDraft";
import { EFFORT_PROFILES, type EffortKey } from "../../copy/terms";
import { readTheme, writeTheme, THEMES, type ThemeChoice } from "../../theme";
import { restartOnboarding } from "../Onboarding/onboarding";
import { useToast } from "../shared/Toast";

/**
 * One home for every preference the phase introduced (SPEC-052).
 *
 * Theme (SPEC-045), reading altitude (SPEC-048), default effort and
 * watch-or-notify (SPEC-050), notification permission (SPEC-051) and the
 * onboarding tour all accumulated as `localStorage` keys set from whichever
 * screen happened to introduce them. A preference you can only change by
 * re-doing the action that set it is not a preference.
 *
 * Preferences only. Nothing here touches a case.
 */
export function Settings() {
  const [altitude, setAltitude] = useAltitude();
  const [presence, setPresenceState] = useState<Presence>(getPresence);
  const [theme, setThemeState] = useState<ThemeChoice>(readTheme);
  const [effort, setEffort] = useState<EffortKey>(() => readDraft().effort);
  const [permission, setPermission] = useState(permissionState);
  const toast = useToast();

  useEffect(() => setPermission(permissionState()), []);

  function chooseEffort(key: EffortKey) {
    setEffort(key);
    writeDraft({ ...readDraft(), effort: key });
  }

  function chooseTheme(choice: ThemeChoice) {
    setThemeState(choice);
    // Applied immediately, not on reload: a theme control that needs a refresh
    // to show its effect is a control nobody trusts.
    writeTheme(choice);
  }

  return (
    <div className="settings">
      <h2>Settings</h2>
      <p className="screen-help">
        These are preferences about how you like to work. None of them change what a case does or
        what it records.
      </p>

      <Group legend="Appearance" help="Applies immediately, everywhere.">
        {THEMES.map((t) => (
          <Choice
            key={t.key}
            selected={theme === t.key}
            onClick={() => chooseTheme(t.key)}
            label={t.label}
            blurb={t.blurb}
          />
        ))}
      </Group>

      <Group legend="How much detail to show" help="Applies to every case you open.">
        {ALTITUDES.map((a) => (
          <Choice
            key={a.key}
            selected={altitude === a.key}
            onClick={() => setAltitude(a.key)}
            label={a.label}
            blurb={a.blurb}
          />
        ))}
      </Group>

      <Group legend="Default depth for a new decision" help="You can still change it per case.">
        {(Object.keys(EFFORT_PROFILES) as EffortKey[]).map((key) => (
          <Choice
            key={key}
            selected={effort === key}
            onClick={() => chooseEffort(key)}
            label={EFFORT_PROFILES[key].label}
            blurb={EFFORT_PROFILES[key].blurb}
          />
        ))}
      </Group>

      <Group legend="While a case runs" help="">
        <Choice
          selected={presence === "watch"}
          onClick={() => {
            setPresence("watch");
            setPresenceState("watch");
          }}
          label="I'll watch"
          blurb="No notifications for gates you are looking at."
        />
        <Choice
          selected={presence === "notify"}
          onClick={() => {
            setPresence("notify");
            setPresenceState("notify");
          }}
          label="Ping me"
          blurb="Tell me when a case needs a decision from me."
        />
      </Group>

      <section className="settings-group">
        <h3>Notifications</h3>
        <p className="settings-permission">
          {permission === "granted"
            ? "This browser will show notifications from AgentAdvisor."
            : permission === "denied"
              ? "This browser is blocking notifications. Notices will appear in the page instead — the block can only be lifted in browser settings."
              : permission === "unsupported"
                ? "This browser does not support notifications. Notices will appear in the page instead."
                : "Not asked yet. You will be asked the first time a case starts running."}
        </p>
        {permission === "default" && (
          <button
            type="button"
            className="secondary-action"
            onClick={async () => {
              const result = await requestPermissionOnRun();
              setPermission(result);
              toast.show(
                result === "granted" ? "Notifications enabled." : "Notifications not enabled.",
                result === "granted" ? "success" : "info",
              );
            }}
          >
            Enable notifications
          </button>
        )}
      </section>

      <section className="settings-group">
        <h3>The tour</h3>
        <p className="screen-help">
          Replays a recorded case at speed, showing a full deliberation with its loops and its
          disagreement.
        </p>
        <Link
          to="/onboarding"
          className="secondary-action"
          onClick={() => restartOnboarding()}
        >
          Run the tour again
        </Link>
      </section>
    </div>
  );
}

function Group({
  legend,
  help,
  children,
}: {
  legend: string;
  help: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="settings-group">
      <legend>{legend}</legend>
      {help && <p className="screen-help">{help}</p>}
      <div className="settings-choices">{children}</div>
    </fieldset>
  );
}

function Choice({
  selected,
  onClick,
  label,
  blurb,
}: {
  selected: boolean;
  onClick: () => void;
  label: string;
  blurb: string;
}) {
  return (
    <button
      type="button"
      className={`settings-choice${selected ? " selected" : ""}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span className="settings-choice-label">{label}</span>
      <span className="settings-choice-blurb">{blurb}</span>
    </button>
  );
}
