import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, Trash2 } from "lucide-react";
import { useCallback, useRef, useState } from "react";

const EASE = [0.16, 1, 0.3, 1];

export const people = (n) => `${n} ${n > 1 ? "personnes" : "personne"}`;

/** Checkout state -> [key, label]. Closed beats busy: an unstaffed till serves no one. */
export function checkoutState(c) {
  if (!c.is_open) return ["closed", "Fermée"];
  return c.is_occupied ? ["busy", "Occupée"] : ["free", "Libre"];
}

/** Drawn state geometry, so state never relies on colour alone (SYSTEM_DESIGN §3.3). */
export function StatusShape({ state, size = 8 }) {
  const r = size / 2;
  return (
    <svg className="shape" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {state === "free" && <circle cx={r} cy={r} r={r} fill="currentColor" />}
      {state === "busy" && <rect width={size} height={size} rx={1} fill="currentColor" />}
      {state === "closed" && <circle cx={r} cy={r} r={r - 1} fill="none" stroke="currentColor" strokeWidth="1.5" />}
    </svg>
  );
}

/** Badge whose label cross-fades when the state changes. */
export function StatusBadge({ state, label }) {
  return (
    <span className={`badge badge-${state}`}>
      <StatusShape state={state} />
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span key={state} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          {label}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function LiveIndicator({ online }) {
  return online ? (
    <span className="live live-on"><StatusShape state="free" />En direct</span>
  ) : (
    <span className="live live-off"><StatusShape state="closed" />Hors ligne</span>
  );
}

/** Digits roll in the direction of change: up when the queue grows, down when it shrinks. */
export function RollingNumber({ value, className = "" }) {
  const prev = useRef(value);
  const dir = value > prev.current ? 1 : -1;
  prev.current = value;
  return (
    <span className={`roll ${className}`}>
      <AnimatePresence mode="popLayout" initial={false} custom={dir}>
        <motion.span
          key={value}
          custom={dir}
          variants={{
            enter: (d) => ({ transform: `translateY(${d * 60}%)`, opacity: 0 }),
            center: { transform: "translateY(0%)", opacity: 1 },
            exit: (d) => ({ transform: `translateY(${-d * 60}%)`, opacity: 0 }),
          }}
          initial="enter"
          animate="center"
          exit="exit"
          transition={{ duration: 0.24, ease: EASE }}
        >
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

/** One-shot highlight when `trigger` changes; opacity only, so it stays on the compositor. */
export function Flash({ trigger, color }) {
  const seen = useRef(trigger);
  const changed = useRef(false);
  if (trigger !== seen.current) {
    seen.current = trigger;
    changed.current = true;
  }
  if (!changed.current) return null; // never flash on first paint, only on a real change
  return (
    <motion.span
      key={trigger}
      className="flash"
      style={{ "--c": color }}
      initial={{ opacity: 1 }}
      animate={{ opacity: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      aria-hidden="true"
    />
  );
}

export function useToasts() {
  const [items, setItems] = useState([]);
  const show = useCallback((text) => {
    const id = crypto.randomUUID();
    setItems((t) => [...t, { id, text }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  const view = (
    <div className="toasts" role="status" aria-live="polite">
      <AnimatePresence>
        {items.map((t) => (
          <motion.div
            key={t.id}
            className="toast"
            initial={{ opacity: 0, transform: "translateY(12px)" }}
            animate={{ opacity: 1, transform: "translateY(0px)", transition: { duration: 0.2, ease: EASE } }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
          >
            <CheckCircle2 size={16} aria-hidden="true" />
            {t.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
  return [view, show];
}

/** Staggered enter for tiles and panels, once on mount. */
export const enter = (i = 0) => ({
  initial: { opacity: 0, transform: "translateY(8px)" },
  animate: { opacity: 1, transform: "translateY(0px)" },
  transition: { duration: 0.32, ease: EASE, delay: i * 0.04 },
});

/** Destructive action, isolated and confirmed in place (no modal, no browser dialog). */
export function ConfirmDelete({ label, onConfirm, compact = false }) {
  const [confirming, setConfirming] = useState(false);
  return confirming ? (
    <>
      <button className="btn btn-danger" onClick={onConfirm} autoFocus>Confirmer</button>
      <button className="btn btn-ghost" onClick={() => setConfirming(false)}>Annuler</button>
    </>
  ) : (
    <button className={`btn btn-danger${compact ? " quiet" : ""}`} onClick={() => setConfirming(true)} aria-label={label} title={label}>
      <Trash2 size={14} aria-hidden="true" />{!compact && "Supprimer"}
    </button>
  );
}

/** API errors arrive as DRF JSON; turn them into one readable French sentence. */
export function readableError(err, fallback) {
  try {
    const data = JSON.parse(err.message);
    const first = Object.entries(data)[0];
    if (!first) return fallback;
    const [field, msg] = first;
    const text = Array.isArray(msg) ? msg[0] : msg;
    return field === "detail" || field === "non_field_errors" ? text : `${field} : ${text}`;
  } catch {
    return fallback;
  }
}
