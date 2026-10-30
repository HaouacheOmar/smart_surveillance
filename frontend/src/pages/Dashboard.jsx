import { AnimatePresence, motion } from "motion/react";
import { CameraOff, MapPinned, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Flash, LiveIndicator, RollingNumber, StatusBadge, checkoutState, enter, people } from "../components";

const STALE_AFTER_MS = 10000;
const time = (iso) => new Date(iso).toLocaleTimeString("fr-FR");
const toPoints = (polygon) => polygon.map((p) => p.join(",")).join(" ");
const STATE_COLOR = { free: "var(--state-free)", busy: "var(--state-busy)", closed: "var(--state-closed)" };

function Stream({ camera }) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState(false);
  return (
    <>
      {!loaded && camera.online && <div className="skeleton" aria-hidden="true" />}
      <img
        src={`/stream/${camera.id}?attempt=${attempt}`}
        alt={`Flux annoté de la caméra ${camera.name}`}
        onLoad={() => setLoaded(true)}
        onError={() => { setLoaded(false); setTimeout(() => setAttempt((n) => n + 1), 3000); }}
      />
    </>
  );
}

function CameraTile({ camera, hallways, selection, index }) {
  const zone = selection && hallways.find((h) => h.id === selection.hallwayId);
  const checkout = zone && selection.checkoutId && zone.checkouts.find((c) => c.id === selection.checkoutId);
  const highlight = checkout
    ? { polygon: checkout.polygon, color: STATE_COLOR[checkoutState(checkout)[0]] }
    : zone && { polygon: zone.polygon, color: "var(--zone-hallway)" };

  return (
    <motion.article className="tile" {...enter(index)}>
      <div className={`video${camera.online ? "" : " offline"}`}>
        <Stream camera={camera} />
        {highlight && (
          // Spotlight: everything outside the selected zone dims, so the eye lands on it.
          <motion.svg
            key={`${selection.hallwayId}-${selection.checkoutId}`}
            className="zones" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.24 }}
          >
            <defs>
              <mask id={`spot-${camera.id}`}>
                <rect width="1" height="1" fill="white" />
                <polygon points={toPoints(highlight.polygon)} fill="black" />
                {checkout?.staff_polygon && <polygon points={toPoints(checkout.staff_polygon)} fill="black" />}
              </mask>
            </defs>
            <rect width="1" height="1" fill="rgb(13 17 23 / 0.62)" mask={`url(#spot-${camera.id})`} />
            <polygon className="selected-poly" style={{ "--c": highlight.color }} points={toPoints(highlight.polygon)} />
            {checkout?.staff_polygon && (
              <polygon className="selected-poly" style={{ "--c": "var(--zone-staff)" }} points={toPoints(checkout.staff_polygon)} />
            )}
          </motion.svg>
        )}
        <LiveIndicator online={camera.online} />
        {!camera.online && (
          <div className="notice"><CameraOff size={20} aria-hidden="true" />Caméra hors ligne, reconnexion…</div>
        )}
      </div>
      <div className="tile-foot">
        <strong>{camera.name}</strong>
        {hallways.length === 0 ? (
          <a className="btn btn-ghost" href={`#/mapping/${camera.id}`}><MapPinned size={14} aria-hidden="true" />Cartographier</a>
        ) : (
          <span className="muted">{hallways.map((h) => h.name).join(" · ")}</span>
        )}
      </div>
    </motion.article>
  );
}

function HallwayPanel({ hallway, online, selection, onSelect }) {
  const isSel = (checkoutId) => selection?.hallwayId === hallway.id && selection.checkoutId === checkoutId;
  return (
    <div className="hall">
      <button className="hall-head" aria-pressed={isSel(undefined)} onClick={() => onSelect({ hallwayId: hallway.id })}>
        <span>
          <span className="hall-name">{hallway.name}</span>
          <span className="hall-sub">{online ? "en attente" : "données indisponibles"}</span>
        </span>
        <span className="hall-count">{online ? <RollingNumber value={hallway.people_count} /> : "–"}</span>
      </button>
      <ul className="checkouts">
        {hallway.checkouts.map((c) => {
          const [state, label] = online ? checkoutState(c) : ["closed", "Inconnu"];
          return (
            <li key={c.id}>
              <button className="checkout-row" aria-pressed={isSel(c.id)} onClick={() => onSelect({ hallwayId: hallway.id, checkoutId: c.id })}>
                <Flash trigger={state} color={STATE_COLOR[state]} />
                <span>{c.name}</span>
                <StatusBadge state={state} label={label} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Inspector({ selection, hallways, cameras }) {
  const hallway = hallways.find((h) => h.id === selection?.hallwayId);
  if (!hallway) return null;
  const camera = cameras.find((c) => c.id === hallway.camera);
  const checkout = hallway.checkouts.find((c) => c.id === selection.checkoutId);
  const rows = checkout
    ? [
        ["État", checkoutState(checkout)[1]],
        ["Couloir", hallway.name],
        ["Zone caissier", checkout.staff_polygon ? "définie" : "non définie"],
        ["Dernier changement", time(checkout.updated_at)],
        ["Caméra", camera?.name ?? "–"],
      ]
    : [
        ["En attente", people(hallway.people_count)],
        ["Caisses ouvertes", `${hallway.checkouts.filter((c) => c.is_open).length}/${hallway.checkouts.length}`],
        ["Dernier changement", time(hallway.updated_at)],
        ["Caméra", camera?.name ?? "–"],
      ];
  return (
    <motion.div
      key={`${selection.hallwayId}-${selection.checkoutId}`}
      className="inspector"
      initial={{ opacity: 0, transform: "translateY(8px)" }}
      animate={{ opacity: 1, transform: "translateY(0px)" }}
      exit={{ opacity: 0, transition: { duration: 0.12 } }}
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="panel-head">Inspecteur · {checkout?.name ?? hallway.name}</div>
      {rows.map(([k, v]) => <div className="kv" key={k}><span>{k}</span><span>{v}</span></div>)}
    </motion.div>
  );
}

/** Recent state changes (OccupancyLog is written only on change), newest first. */
function Activity({ hallways }) {
  const [logs, setLogs] = useState([]);
  useEffect(() => {
    const load = () => api("/occupancy-logs/").then((page) => setLogs(page.results.slice(0, 12)), () => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);
  const name = (id) => hallways.find((h) => h.id === id)?.name ?? "Couloir supprimé";
  return (
    <>
      <div className="panel-head">Activité<span className="end">changements d'état récents</span></div>
      {logs.length === 0 ? (
        <div className="empty"><span>Aucun changement enregistré pour l'instant.</span></div>
      ) : (
        <ul className="activity">
          <AnimatePresence initial={false}>
            {logs.map((l) => (
              <motion.li key={l.id} layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                <time dateTime={l.created_at}>{time(l.created_at)}</time>
                <span>{name(l.hallway)}</span>
                <span className="n">{people(l.people_count)}</span>
                <span className="free-col muted">{l.free_checkouts} {l.free_checkouts > 1 ? "caisses libres" : "caisse libre"}</span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </>
  );
}

export default function Dashboard() {
  const [cameras, setCameras] = useState();
  const [hallways, setHallways] = useState([]);
  const [selection, setSelection] = useState(null);
  const [lastSync, setLastSync] = useState(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const loadCameras = () => api("/cameras/").then(setCameras, () => {});
    const loadHallways = () => api("/hallways/").then((h) => { setHallways(h); setLastSync(Date.now()); }, () => {});
    loadCameras(); loadHallways();
    const timers = [setInterval(loadHallways, 2000), setInterval(loadCameras, 10000), setInterval(() => setNow(Date.now()), 1000)];
    return () => timers.forEach(clearInterval);
  }, []);

  if (cameras === undefined) return null;
  const active = cameras.filter((c) => c.is_active);
  if (!active.length) {
    return (
      <div className="empty">
        <strong>Aucune caméra configurée</strong>
        <span>Ajoutez une caméra puis tracez ses couloirs et caisses pour commencer la supervision.</span>
        <a className="btn btn-primary" href="#/cameras"><Plus size={16} aria-hidden="true" />Ajouter une caméra</a>
      </div>
    );
  }

  const online = (cameraId) => cameras.find((c) => c.id === cameraId)?.online;
  const stale = !lastSync || now - lastSync > STALE_AFTER_MS;
  const waiting = hallways.filter((h) => online(h.camera)).reduce((n, h) => n + h.people_count, 0);
  const free = hallways.flatMap((h) => (online(h.camera) ? h.checkouts : [])).filter((c) => checkoutState(c)[0] === "free").length;
  const toggle = (sel) => setSelection((s) => (s?.hallwayId === sel.hallwayId && s.checkoutId === sel.checkoutId ? null : sel));

  return (
    <div className="console">
      <section aria-label="Caméras">
        <div className="panel-head">
          Caméras
          <span className="end mono">{active.filter((c) => c.online).length} en direct · {active.filter((c) => !c.online).length} hors ligne</span>
        </div>
        <div className="tiles">
          {active.map((c, i) => (
            <CameraTile key={c.id} camera={c} index={i} hallways={hallways.filter((h) => h.camera === c.id)} selection={selection} />
          ))}
        </div>
        <Activity hallways={hallways} />
      </section>
      <aside className="side" aria-label="Couloirs et caisses">
        <div className="panel-head">
          Couloirs
          <span className="end mono" style={{ color: stale ? "var(--state-busy)" : undefined }}>
            {stale ? "données périmées" : `maj il y a ${Math.max(0, Math.round((now - lastSync) / 1000))} s`}
          </span>
        </div>
        <span className="sr-only" role="status" aria-atomic="true">{people(waiting)} en attente, {free} {free > 1 ? "caisses libres" : "caisse libre"}</span>
        {hallways.length === 0 && (
          <div className="empty"><span>Aucun couloir cartographié. Ouvrez une caméra et tracez ses zones.</span></div>
        )}
        {hallways.map((h) => (
          <HallwayPanel key={h.id} hallway={h} online={online(h.camera)} selection={selection} onSelect={toggle} />
        ))}
        <AnimatePresence mode="wait">
          {selection && <Inspector selection={selection} hallways={hallways} cameras={cameras} />}
        </AnimatePresence>
      </aside>
    </div>
  );
}
