import { AlertCircle, ArrowLeft, RotateCcw, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ConfirmDelete, readableError, useToasts } from "../components";

const toPoints = (polygon) => polygon.map((p) => p.join(",")).join(" ");
const TOOLS = {
  hallway: { label: "Couloir", color: "var(--zone-hallway)" },
  checkout: { label: "Caisse (côté client)", color: "var(--state-free)" },
  staff: { label: "Zone caissier", color: "var(--zone-staff)" },
};

export default function Mapping({ cameraId, isAdmin }) {
  const [camera, setCamera] = useState();
  const [image, setImage] = useState();
  const [snapError, setSnapError] = useState(false);
  const [hallways, setHallways] = useState([]);
  const [tool, setTool] = useState("hallway");
  const [parent, setParent] = useState(""); // hallway id for a checkout, checkout id for a cashier zone
  const [points, setPoints] = useState([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [toasts, toast] = useToasts();
  const form = useRef(null);

  const load = () => api(`/hallways/?camera=${cameraId}`).then(setHallways);
  const snapshot = () => {
    setSnapError(false);
    setImage(undefined);
    return api(`/cameras/${cameraId}/snapshot/`, { raw: true }).then(
      (blob) => setImage(URL.createObjectURL(blob)),
      () => setSnapError(true),
    );
  };

  useEffect(() => {
    api(`/cameras/${cameraId}/`).then(setCamera, () => {});
    snapshot();
    load();
  }, [cameraId]);
  useEffect(() => () => image && URL.revokeObjectURL(image), [image]);

  const checkouts = hallways.flatMap((h) => h.checkouts.map((c) => ({ ...c, hallwayName: h.name })));
  const needsParent = tool !== "hallway";
  const parentOptions = tool === "checkout" ? hallways.map((h) => [h.id, h.name]) : checkouts.map((c) => [c.id, `${c.name} (${c.hallwayName})`]);
  const canSave = points.length >= 3 && (!needsParent || parent) && (tool === "staff" || name.trim());

  useEffect(() => { setParent(""); }, [tool]);

  // Keyboard: Enter saves, Esc clears the draft, Backspace removes the last point (outside text fields).
  useEffect(() => {
    if (!isAdmin) return;
    const onKey = (e) => {
      const typing = e.target.matches?.("input, select, textarea");
      if (e.key === "Escape") setPoints([]);
      else if (e.key === "Backspace" && !typing) { e.preventDefault(); setPoints((p) => p.slice(0, -1)); }
      else if (e.key === "Enter" && !typing && canSave) form.current?.requestSubmit();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [isAdmin, canSave]);

  const addPoint = (e) => {
    if (!isAdmin) return;
    const r = e.currentTarget.getBoundingClientRect();
    const p = [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height].map((v) => Math.min(1, Math.max(0, +v.toFixed(4))));
    setPoints((pts) => [...pts, p]);
  };

  const save = async (e) => {
    e.preventDefault();
    if (!canSave) return;
    try {
      if (tool === "hallway") await api("/hallways/", { method: "POST", body: { camera: +cameraId, name, polygon: points } });
      if (tool === "checkout") await api("/checkouts/", { method: "POST", body: { hallway: +parent, name, polygon: points } });
      if (tool === "staff") await api(`/checkouts/${parent}/`, { method: "PATCH", body: { staff_polygon: points } });
      toast(tool === "staff" ? "Zone caissier enregistrée" : `« ${name} » enregistré`);
      setPoints([]); setName(""); setError("");
      load();
    } catch (err) {
      setError(readableError(err, "Enregistrement impossible. Vérifiez le tracé et réessayez."));
    }
  };

  const remove = (kind, id, label) => api(`/${kind}/${id}/`, { method: "DELETE" }).then(() => { toast(`« ${label} » supprimé`); load(); });
  const removeStaff = (c) => api(`/checkouts/${c.id}/`, { method: "PATCH", body: { staff_polygon: null } }).then(() => { toast("Zone caissier retirée"); load(); });
  const draftColor = TOOLS[tool].color;

  return (
    <div className="mapping">
      <section aria-label="Cartographie">
        <div className="panel-head">
          <a className="btn btn-ghost" href="#/cameras" aria-label="Retour aux caméras"><ArrowLeft size={14} aria-hidden="true" /></a>
          Cartographie · {camera?.name ?? "…"}
          <button className="btn btn-ghost end" onClick={snapshot}><RotateCcw size={14} aria-hidden="true" />Nouvelle capture</button>
        </div>

        {isAdmin && (
          <div className="toolbar" role="group" aria-label="Type de zone">
            {Object.entries(TOOLS).map(([key, t]) => (
              <button key={key} className="tool" style={{ "--c": t.color }} aria-pressed={tool === key} onClick={() => setTool(key)}>
                <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="2" fill={t.color} /></svg>
                {t.label}
              </button>
            ))}
            <span className="shortcuts">
              <span className="kbd">Entrée</span> enregistrer · <span className="kbd">Échap</span> effacer · <span className="kbd">⌫</span> dernier point
            </span>
          </div>
        )}

        <div className="canvas">
          {image ? <img src={image} alt={`Capture de la caméra ${camera?.name ?? ""} pour cartographier les zones`} />
            : snapError ? (
              <div className="empty">
                <div className="alert" role="alert"><AlertCircle size={16} aria-hidden="true" />Caméra injoignable. Vérifiez l'URL RTSP et que la caméra est allumée.</div>
                <button className="btn btn-secondary" onClick={snapshot}><RotateCcw size={14} aria-hidden="true" />Réessayer</button>
              </div>
            ) : <div style={{ aspectRatio: "16 / 9", position: "relative" }}><div className="skeleton" /></div>}
          {image && (
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" onClick={addPoint} aria-label="Zone de tracé">
              {hallways.map((h) => (
                <g key={h.id}>
                  <polygon className="z-hallway" points={toPoints(h.polygon)} />
                  {h.checkouts.map((c) => (
                    <g key={c.id}>
                      <polygon className="z-checkout" points={toPoints(c.polygon)} />
                      {c.staff_polygon && <polygon className="z-staff" points={toPoints(c.staff_polygon)} />}
                    </g>
                  ))}
                </g>
              ))}
              {points.length > 1 && <polygon className="z-draft" style={{ "--c": draftColor }} points={toPoints(points)} />}
              {points.map(([x, y], i) => (
                <circle key={i} className="vertex" style={{ "--c": draftColor }} cx={x} cy={y} r="0.006" />
              ))}
            </svg>
          )}
        </div>
      </section>

      <aside className="side" aria-label="Zones">
        {isAdmin && (
          <form ref={form} className="form" onSubmit={save}>
            <div className="field">
              <span>Nouveau tracé · {TOOLS[tool].label}</span>
              <span className="draft-status" aria-live="polite">
                {points.length} point{points.length > 1 ? "s" : ""} — {points.length < 3 ? `encore ${3 - points.length} minimum` : "prêt à enregistrer"}
              </span>
            </div>
            {needsParent && (
              <label className="field">
                <span>{tool === "checkout" ? "Dans le couloir" : "Pour la caisse"}</span>
                <select className="input" value={parent} onChange={(e) => setParent(e.target.value)} required>
                  <option value="">Choisir…</option>
                  {parentOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                </select>
              </label>
            )}
            {tool !== "staff" && (
              <label className="field">
                <span>Nom</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder={tool === "hallway" ? "Couloir A" : "Caisse 1"} required />
              </label>
            )}
            {error && <div className="alert" role="alert"><AlertCircle size={16} aria-hidden="true" />{error}</div>}
            <button className="btn btn-primary" disabled={!canSave}><Save size={16} aria-hidden="true" />Enregistrer la zone</button>
          </form>
        )}

        <div className="panel-head">Zones de cette caméra</div>
        {hallways.length === 0 && <div className="empty"><span>Aucune zone. Commencez par tracer un couloir.</span></div>}
        <ul className="zone-list">
          {hallways.map((h) => [
            <li key={`h${h.id}`}>
              <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="2" fill="var(--zone-hallway)" /></svg>
              <span className="name">{h.name}</span>
              {isAdmin && <ConfirmDelete compact label={`Supprimer le couloir ${h.name} et ses caisses`} onConfirm={() => remove("hallways", h.id, h.name)} />}
            </li>,
            ...h.checkouts.flatMap((c) => [
              <li key={`c${c.id}`} className="child">
                <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="2" fill="var(--state-free)" /></svg>
                <span className="name">{c.name}</span>
                {isAdmin && <ConfirmDelete compact label={`Supprimer la caisse ${c.name}`} onConfirm={() => remove("checkouts", c.id, c.name)} />}
              </li>,
              c.staff_polygon && (
                <li key={`s${c.id}`} className="child">
                  <svg width="10" height="10" aria-hidden="true"><rect x="1" y="1" width="8" height="8" rx="2" fill="none" stroke="var(--zone-staff)" strokeWidth="1.5" strokeDasharray="2 1.5" /></svg>
                  <span className="name muted">Zone caissier · {c.name}</span>
                  {isAdmin && <ConfirmDelete compact label={`Retirer la zone caissier de ${c.name}`} onConfirm={() => removeStaff(c)} />}
                </li>
              ),
            ]),
          ])}
        </ul>
      </aside>
      {toasts}
    </div>
  );
}
