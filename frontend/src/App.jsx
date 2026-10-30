import { MotionConfig } from "motion/react";
import { Camera, LayoutDashboard, LogOut, MonitorPlay, ScanEye } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import Cameras from "./pages/Cameras";
import Dashboard from "./pages/Dashboard";
import Lcd from "./pages/Lcd";
import Login from "./pages/Login";
import Mapping from "./pages/Mapping";

function useHash() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const onChange = () => setHash(location.hash);
    addEventListener("hashchange", onChange);
    return () => removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const [user, setUser] = useState(); // undefined = loading, null = logged out

  useEffect(() => {
    api("/auth/me/").then(setUser, () => setUser(null));
    const onLogout = () => setUser(null);
    addEventListener("logout", onLogout);
    return () => removeEventListener("logout", onLogout);
  }, []);

  if (hash === "#/lcd") return <MotionConfig reducedMotion="user"><Lcd /></MotionConfig>; // public screen
  if (user === undefined) return null;
  if (!user) return <MotionConfig reducedMotion="user"><Login onLogin={setUser} /></MotionConfig>;

  const [, page = "", id] = hash.split("/");
  const current = page === "mapping" ? "cameras" : page || "supervision";
  const logout = () => api("/auth/logout/", { method: "POST" }).finally(() => setUser(null));
  const link = (key, href, Icon, label) => (
    <a href={href} aria-current={current === key ? "page" : undefined}>
      <Icon size={16} aria-hidden="true" /><span>{label}</span>
    </a>
  );

  return (
    <MotionConfig reducedMotion="user">
      <div className="shell">
        <header className="topbar">
          <span className="brand"><ScanEye size={18} aria-hidden="true" /><span>Smart Surveillance</span></span>
          <nav className="nav" aria-label="Navigation principale">
            {link("supervision", "#/", LayoutDashboard, "Supervision")}
            {link("cameras", "#/cameras", Camera, "Caméras")}
            <a href="#/lcd" target="_blank" rel="noreferrer"><MonitorPlay size={16} aria-hidden="true" /><span>Écran LCD</span></a>
          </nav>
          <span className="spacer" />
          <span className="user">
            <span className="name">{user.username}</span>
            <button className="btn btn-ghost" onClick={logout} aria-label="Se déconnecter">
              <LogOut size={16} aria-hidden="true" />
            </button>
          </span>
        </header>
        <main className="page">
          {page === "cameras" ? <Cameras isAdmin={user.is_admin} />
            : page === "mapping" && id ? <Mapping cameraId={id} isAdmin={user.is_admin} />
            : <Dashboard />}
        </main>
      </div>
    </MotionConfig>
  );
}
