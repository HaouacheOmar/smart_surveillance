import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Loader2, MapPinned, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { ConfirmDelete, LiveIndicator, readableError, useToasts } from "../components";

const FIELDS = [
  ["name", "Nom", { placeholder: "Entrée principale", autoComplete: "off" }],
  ["ip_address", "Adresse IP", { placeholder: "192.168.1.20", className: "input mono", inputMode: "decimal" }],
  ["rtsp_url", "URL RTSP", { placeholder: "rtsp://192.168.1.20:554/stream1", className: "input mono" }],
  ["username", "Utilisateur RTSP", { autoComplete: "off", required: false }],
  ["password", "Mot de passe RTSP", { type: "password", autoComplete: "new-password", required: false }],
];

export default function Cameras({ isAdmin }) {
  const [cameras, setCameras] = useState();
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [toasts, toast] = useToasts();
  const load = () => api("/cameras/").then(setCameras, () => setCameras([]));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    setSaving(true);
    try {
      const created = await api("/cameras/", { method: "POST", body: Object.fromEntries(new FormData(form)) });
      form.reset();
      setErrors({});
      toast(`Caméra « ${created.name} » ajoutée`);
      load();
    } catch (err) {
      try {
        setErrors(Object.fromEntries(Object.entries(JSON.parse(err.message)).map(([k, v]) => [k, [].concat(v)[0]])));
      } catch {
        setErrors({ form: readableError(err, "Impossible d'ajouter la caméra. Réessayez.") });
      }
    } finally {
      setSaving(false);
    }
  };

  const remove = async (camera) => {
    await api(`/cameras/${camera.id}/`, { method: "DELETE" });
    toast(`Caméra « ${camera.name} » supprimée`);
    load();
  };

  return (
    <div className="config">
      <section aria-label="Liste des caméras">
        <div className="panel-head">Caméras<span className="end mono">{cameras?.length ?? 0} {(cameras?.length ?? 0) > 1 ? "configurées" : "configurée"}</span></div>
        {cameras && cameras.length === 0 ? (
          <div className="empty">
            <strong>Aucune caméra</strong>
            <span>Ajoutez la première caméra avec son adresse IP et son URL RTSP.</span>
          </div>
        ) : (
          <table className="table">
            <thead><tr><th>Nom</th><th>Adresse IP</th><th>URL RTSP</th><th>État</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              <AnimatePresence initial={false}>
                {cameras?.map((c) => (
                  <motion.tr key={c.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
                    <td><strong>{c.name}</strong></td>
                    <td className="mono">{c.ip_address}</td>
                    <td><div className="url mono" title={c.rtsp_url}>{c.rtsp_url}</div></td>
                    <td><LiveIndicator online={c.online} /></td>
                    <td>
                      <div className="row-actions">
                        <a className="btn btn-ghost" href={`#/mapping/${c.id}`}><MapPinned size={14} aria-hidden="true" />Zones</a>
                        {isAdmin && <><span className="gap" /><ConfirmDelete compact label={`Supprimer la caméra ${c.name} et ses zones`} onConfirm={() => remove(c)} /></>}
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        )}
      </section>

      {isAdmin && (
        <form className="form" onSubmit={add} noValidate={false} aria-labelledby="add-title">
          <h2 id="add-title" className="page-title">Ajouter une caméra</h2>
          <p className="hint">Le mot de passe est chiffré et n'est jamais réaffiché. Saisissez l'URL sans identifiants.</p>
          {errors.form && <div className="alert" role="alert"><AlertCircle size={16} aria-hidden="true" />{errors.form}</div>}
          {FIELDS.map(([name, label, { className = "input", required = true, ...rest }]) => (
            <label className="field" key={name}>
              <span>{label}</span>
              <input name={name} className={className} required={required} aria-invalid={!!errors[name]} aria-describedby={errors[name] ? `${name}-err` : undefined} {...rest} />
              {errors[name] && <span id={`${name}-err`} className="field-error">{errors[name]}</span>}
            </label>
          ))}
          <button className="btn btn-primary" disabled={saving}>
            {saving ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}
            Ajouter la caméra
          </button>
        </form>
      )}
      {toasts}
    </div>
  );
}
