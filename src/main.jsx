import React from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowRight, CalendarClock, CheckCircle2, Files, Menu, ScanLine, Sparkles, Users } from 'lucide-react';
import './styles.css';

const pipeline = [
  { step: '01', title: 'Source intake', text: 'Collect candidate signals, resumes, notes, and role requirements into one structured hiring workspace.' },
  { step: '02', title: 'Screening logic', text: 'Rank fit, flag missing evidence, and route profiles to the right reviewer without manual triage.' },
  { step: '03', title: 'Interview rhythm', text: 'Coordinate calendars, scorecards, reminders, and next steps with a consistent audit trail.' },
  { step: '04', title: 'Offer readiness', text: 'Prepare decision packets, approvals, and candidate communications before momentum goes cold.' }
];

const metrics = [
  ['42%', 'less manual sorting'],
  ['18h', 'saved per recruiter'],
  ['4.8x', 'faster shortlist']
];

function App() {
  return (
    <main className="app-shell">
      <div className="system-strip">
        <span>HR SYSTEM</span>
        <span>JUL 14 2026</span>
        <span>AUTOMATION CONSOLE READY</span>
      </div>

      <header className="site-header">
        <a className="ghost-pill" href="#workspace">
          Start now <ArrowRight size={15} strokeWidth={1.5} />
        </a>
        <div className="brand-mark" aria-label="HR Automata">
          <span className="brand-symbol" />
          <span>HR AUTOMATA</span>
        </div>
        <button className="ghost-pill" type="button">
          Menu <Menu size={15} strokeWidth={1.5} />
        </button>
      </header>

      <section className="hero-section">
        <div className="ambient-orbit ambient-orbit-one" />
        <div className="ambient-orbit ambient-orbit-two" />
        <p className="hero-flank hero-flank-left">Automate the mundane</p>
        <div className="hero-core">
          <div className="constellation">
            <span />
            <span />
            <span />
            <span />
          </div>
          <h1>HR AUTOMATA</h1>
          <p>Hiring operations shaped as one quiet system: intake, screening, interviews, approvals, and candidate movement.</p>
        </div>
        <p className="hero-flank hero-flank-right">Accelerate decisions</p>
      </section>

      <section className="proof-band" aria-label="Operating metrics">
        {metrics.map(([value, label]) => (
          <div className="metric" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>

      <section className="section-block" id="workspace">
        <div className="section-heading">
          <span>AI TRANSFORMATION</span>
          <h2>Systems, not spreadsheets</h2>
          <p>Convert fragmented recruiting work into a controlled operating layer with traceable candidate movement and fewer manual handoffs.</p>
        </div>

        <div className="workspace-grid">
          <article className="featured-panel">
            <div className="panel-topline">
              <span className="pill-badge">LIVE</span>
              <ScanLine size={18} strokeWidth={1.5} />
            </div>
            <h3>Candidate command chamber</h3>
            <p>One surface for role demand, candidate evidence, recruiter actions, and leadership approvals.</p>
            <div className="queue-list">
              <div><Users size={16} /> Senior product analyst <span>12 profiles</span></div>
              <div><Files size={16} /> Compliance reviewer <span>8 profiles</span></div>
              <div><CalendarClock size={16} /> Engineering manager <span>5 interviews</span></div>
            </div>
          </article>

          {pipeline.map((item) => (
            <article className="system-card" key={item.step}>
              <span className="pill-badge">{item.step}</span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block compact">
        <div className="section-heading">
          <span>OPERATING LAYER</span>
          <h2>Every handoff leaves a signal</h2>
        </div>
        <div className="signal-row">
          <div><CheckCircle2 size={18} /> Evidence-based shortlists</div>
          <div><Sparkles size={18} /> Automated recruiter follow-ups</div>
          <div><ScanLine size={18} /> Structured decision history</div>
        </div>
      </section>

      <footer className="site-footer">
        <span>HR AUTOMATA</span>
        <span>VOID OPS FOR HUMAN TEAMS</span>
      </footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
