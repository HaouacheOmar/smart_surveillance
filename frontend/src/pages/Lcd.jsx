import { ArrowRight, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { RollingNumber, StatusShape, checkoutState } from "../components";

const COLOR = { free: "var(--state-free)", busy: "var(--state-busy)", closed: "var(--state-closed)" };

function HallwayCard({ hallway: h }) {
  if (!h.online) {
    return (
      <article className="lcd-card offline">
        <h2 className="lcd-name">{h.name}</h2>
        <p className="lcd-count"><span className="l">Données indisponibles</span></p>
      </article>
    );
  }
  const states = h.checkouts.map((c) => [c, ...checkoutState(c)]);
  const best = states.find(([, s]) => s === "free")?.[0];
  return (
    <article className="lcd-card" aria-label={`${h.name} : ${h.people_count} ${h.people_count > 1 ? "personnes" : "personne"} en attente`}>
      <h2 className="lcd-name">{h.name}</h2>
      <p className="lcd-count">
        <RollingNumber value={h.people_count} className="n mono" />
        <span className="l">{h.people_count > 1 ? "personnes en attente" : "personne en attente"}</span>
      </p>
      <ul className="lcd-rows">
        {states.map(([c, s, label]) => (
          <li key={c.id} className="lcd-row" style={{ "--c": COLOR[s] }}>
            <StatusShape state={s} size={28} />
            {c.name} — {label.toLowerCase()}
          </li>
        ))}
      </ul>
      {best && <p className="lcd-go"><ArrowRight size="1em" aria-hidden="true" /> Allez à la {best.name}</p>}
    </article>
  );
}

export default function Lcd() {
  const [hallways, setHallways] = useState([]);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    let ws, retry, closed = false;
    const connect = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/display/`);
      ws.onmessage = (e) => { setHallways(JSON.parse(e.data)); setLost(false); };
      ws.onclose = () => {
        if (closed) return;
        setLost(true);
        retry = setTimeout(connect, 2000 + Math.random() * 3000); // jitter: screens don't reconnect in lockstep
      };
    };
    connect();
    // Pushes happen on state changes only; camera going offline and zone edits arrive via this refetch.
    const timer = setInterval(() => api("/display/").then(setHallways, () => {}), 10000);
    return () => { closed = true; clearTimeout(retry); clearInterval(timer); ws.close(); };
  }, []);

  return (
    <div className="lcd">
      {lost && <p className="lcd-banner" role="status"><WifiOff size="1em" aria-hidden="true" />Connexion perdue, nouvelle tentative…</p>}
      {hallways.map((h) => <HallwayCard key={h.id} hallway={h} />)}
    </div>
  );
}
