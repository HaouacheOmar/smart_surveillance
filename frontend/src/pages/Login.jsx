import { motion } from "motion/react";
import { AlertCircle, Loader2, ScanEye } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { enter } from "../components";

export default function Login({ onLogin }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      onLogin(await api("/auth/login/", { method: "POST", body: Object.fromEntries(new FormData(e.currentTarget)) }));
    } catch (err) {
      setError(err.status === 429
        ? "Trop de tentatives. Patientez une minute avant de réessayer."
        : "Identifiant ou mot de passe incorrect.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <motion.div className="login" {...enter()}>
        <div className="panel-head"><ScanEye size={14} aria-hidden="true" />Smart Surveillance</div>
        <form onSubmit={submit}>
          <h1 className="page-title">Connexion à la supervision</h1>
          {error && <div className="alert" role="alert"><AlertCircle size={16} aria-hidden="true" />{error}</div>}
          <label className="field"><span>Utilisateur</span><input className="input" name="username" required autoComplete="username" autoFocus /></label>
          <label className="field"><span>Mot de passe</span><input className="input" name="password" type="password" required autoComplete="current-password" /></label>
          <button className="btn btn-primary" disabled={busy}>
            {busy && <Loader2 size={16} className="spin" aria-hidden="true" />}Se connecter
          </button>
        </form>
      </motion.div>
    </div>
  );
}
