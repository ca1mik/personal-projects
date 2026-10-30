import { useState, useEffect } from 'react'
import BIO from './bio.js'
import './App.css'

/* ══════════════════════════════════════════
   UTILITIES
══════════════════════════════════════════ */
function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button className="copy-btn" onClick={copy} title="Скопировать">
      {copied ? '✓ Скопировано' : '⎘ Копировать'}
    </button>
  )
}

/* ══════════════════════════════════════════
   AVATAR
══════════════════════════════════════════ */
function Avatar() {
  if (BIO.avatar) return <img src={BIO.avatar} className="avatar" alt={BIO.name} />
  const initials = BIO.name.split(' ').map(w => w[0]).join('')
  return <div className="avatar avatar-placeholder">{initials}</div>
}

/* ══════════════════════════════════════════
   ICONS
══════════════════════════════════════════ */
const ICONS = {
  telegram: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L8.32 14.617l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.828.942z" />
    </svg>
  ),
  email: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  ),
  phone: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  ),
  location: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  briefcase: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  ),
  edu: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
      <path d="m22 10-10-5L2 10l10 5 10-5z" />
      <path d="M6 12v5c3 3 9 3 12 0v-5" />
    </svg>
  ),
  wallet: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
      <path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z" />
      <path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z" />
      <circle cx="17" cy="13" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  ),
  send: (
    <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15">
      <path d="M2 12L22 2 14 22 11 13z" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  ),
}

/* ══════════════════════════════════════════
   NAVIGATION
══════════════════════════════════════════ */
function Nav({ active, onNav }) {
  const tabs = [
    { id: 'about',      label: 'Обо мне'  },
    { id: 'experience', label: 'Опыт'     },
    { id: 'projects',   label: 'Проекты'  },
    { id: 'feed',       label: 'Посты'    },
    { id: 'contacts',   label: 'Контакты' },
  ]
  return (
    <nav className="nav" role="navigation" aria-label="Разделы">
      {tabs.map(t => (
        <button
          key={t.id}
          id={`nav-${t.id}`}
          className={`nav-btn ${active === t.id ? 'active' : ''}`}
          onClick={() => onNav(t.id)}
          aria-selected={active === t.id}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}

/* ══════════════════════════════════════════
   ABOUT SECTION
══════════════════════════════════════════ */
function AboutSection() {
  return (
    <section className="section" aria-label="Обо мне">
      <p className="about-text">{BIO.description}</p>

      <div className="info-grid">
        <div className="info-item">
          {ICONS.location}
          <div>
            <span className="info-label">Локация</span>
            <span className="info-value">{BIO.location}</span>
          </div>
        </div>
        <div className="info-item">
          {ICONS.briefcase}
          <div>
            <span className="info-label">Опыт</span>
            <span className="info-value">{BIO.experience}</span>
          </div>
        </div>
        <div className="info-item">
          {ICONS.edu}
          <div>
            <span className="info-label">Образование</span>
            <span className="info-value">
              {BIO.education.degree}, {BIO.education.university}
            </span>
          </div>
        </div>
        {BIO.wallet?.address && (
          <div className="info-item">
            {ICONS.wallet}
            <div style={{ overflow: 'hidden', flex: 1 }}>
              <span className="info-label">{BIO.wallet.label} Кошелёк</span>
              <div className="wallet-addr-row" style={{ marginTop: 2 }}>
                <span className="wallet-addr">{BIO.wallet.address}</span>
                <CopyBtn text={BIO.wallet.address} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="subsection">
        <h3 className="subsection-title">Навыки</h3>
        <div className="skills-row">
          {BIO.skills.map(s => <span key={s} className="skill-badge">{s}</span>)}
        </div>
      </div>

      <div className="subsection">
        <h3 className="subsection-title">Языки</h3>
        <div className="langs-row">
          {BIO.languages.map(l => (
            <span key={l.lang} className="lang-badge">
              <strong>{l.lang}</strong> — {l.level}
            </span>
          ))}
        </div>
      </div>

      <div className="subsection">
        <h3 className="subsection-title">Формат работы</h3>
        <div className="format-tags">
          {[
            'Полная занятость', 'Частичная', 'Проектная',
            'Стажировка', 'Гибрид', 'Удалённо', 'Офис',
          ].map(f => (
            <span key={f} className="format-tag">{f}</span>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════
   EXPERIENCE SECTION
══════════════════════════════════════════ */
function ExperienceSection() {
  return (
    <section className="section" aria-label="Опыт работы">
      <div className="timeline">
        {BIO.workExperience.map((job, i) => (
          <div key={i} className="timeline-item">
            <div className="timeline-dot" />
            <div className="timeline-content">
              <div className="job-header">
                <span className="job-period">{job.period}</span>
                <span className="job-duration">{job.duration}</span>
              </div>
              <h3 className="job-position">{job.position}</h3>
              <p className="job-company">
                {job.company}
                {job.industry && <span className="job-industry"> · {job.industry}</span>}
              </p>
              <p className="job-desc">{job.description}</p>
              {job.tasks.length > 0 && (
                <ul className="job-tasks">
                  {job.tasks.map((t, j) => <li key={j}>{t}</li>)}
                </ul>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════
   PROJECTS SECTION
══════════════════════════════════════════ */
function ProjectsSection() {
  return (
    <section className="section" aria-label="Проекты">
      <div className="projects-grid">
        {BIO.projects.map(p => (
          <div key={p.name} className="project-card">
            <div className="project-header">
              <span className="project-icon">🚀</span>
              <h3 className="project-name">{p.name}</h3>
            </div>
            <p className="project-desc">{p.description}</p>
            {p.tags && (
              <div className="project-tags">
                {p.tags.map(t => <span key={t} className="project-tag">{t}</span>)}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════
   FEED SECTION  (Telegram posts)
══════════════════════════════════════════ */
function FeedSection() {
  const [posts, setPosts]     = useState([])
  const [status, setStatus]   = useState('loading') // 'loading' | 'ok' | 'empty' | 'error'

  useEffect(() => {
    fetch('/data/telegram.json')
      .then(r => r.json())
      .then(data => {
        const sorted = [...data].reverse() // newest first
        setPosts(sorted)
        setStatus(sorted.length === 0 ? 'empty' : 'ok')
      })
      .catch(() => setStatus('error'))
  }, [])

  const formatDate = (iso) => {
    const d = new Date(iso)
    return d.toLocaleDateString('ru-RU', {
      day: '2-digit', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  if (status === 'loading') {
    return (
      <section className="section feed-section">
        <div className="feed-empty">
          <span className="feed-empty-icon">⏳</span>
          <p>Загружаем посты…</p>
        </div>
      </section>
    )
  }

  if (status === 'empty' || status === 'error') {
    return (
      <section className="section feed-section">
        <div className="feed-empty">
          <span className="feed-empty-icon">✈️</span>
          <p>
            {status === 'error'
              ? 'Не удалось загрузить посты.'
              : 'Пока нет постов.'}
          </p>
          <a
            href={BIO.contacts.telegramLink}
            target="_blank"
            rel="noopener noreferrer"
            className="feed-channel-link"
            id="feed-channel-btn"
          >
            {ICONS.send}
            Открыть канал {BIO.contacts.telegram}
          </a>
        </div>
      </section>
    )
  }

  return (
    <section className="section feed-section" aria-label="Посты из Telegram">
      <div className="feed-header">
        <a
          href={BIO.contacts.telegramLink}
          target="_blank"
          rel="noopener noreferrer"
          className="feed-channel-link"
          id="feed-channel-btn"
        >
          {ICONS.send}
          {BIO.contacts.telegram}
        </a>
      </div>

      <div className="feed-list">
        {posts.map(post => (
          <article key={post.id} className="feed-card">
            {post.text && <p className="feed-text">{post.text}</p>}
            {!post.text && !post.photo && !post.video && (
              <p className="feed-text feed-text-muted">[медиа-сообщение]</p>
            )}
            {(post.photo || post.video) && !post.text && (
              <p className="feed-text feed-text-muted">
                {post.photo ? '🖼 Фото' : '🎬 Видео'}
              </p>
            )}
            <div className="feed-meta">
              {ICONS.calendar}
              <time dateTime={post.date}>{formatDate(post.date)}</time>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════
   CONTACTS SECTION
══════════════════════════════════════════ */
function ContactsSection() {
  return (
    <section className="section" aria-label="Контакты">
      <div className="contacts-grid">
        <a
          href={`tel:${BIO.contacts.phone.replace(/\s|\(|\)/g, '')}`}
          className="contact-card"
          id="contact-phone"
        >
          {ICONS.phone}
          <div>
            <span className="contact-label">Телефон</span>
            <span className="contact-value">{BIO.contacts.phone}</span>
          </div>
        </a>

        <a href={`mailto:${BIO.contacts.email}`} className="contact-card" id="contact-email">
          {ICONS.email}
          <div>
            <span className="contact-label">Email</span>
            <span className="contact-value">{BIO.contacts.email}</span>
          </div>
        </a>

        <a
          href={BIO.contacts.telegramLink}
          target="_blank"
          rel="noopener noreferrer"
          className="contact-card"
          id="contact-telegram"
        >
          {ICONS.telegram}
          <div>
            <span className="contact-label">Telegram</span>
            <span className="contact-value">{BIO.contacts.telegram}</span>
          </div>
        </a>
      </div>

      <div className="subsection" style={{ marginTop: 8 }}>
        <h3 className="subsection-title">Готов к переезду</h3>
        <p className="about-text">{BIO.relocate}</p>
      </div>

      <div className="subsection">
        <h3 className="subsection-title">Желаемая зарплата</h3>
        <p className="salary-badge">{BIO.salary}</p>
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════
   MAIN APP
══════════════════════════════════════════ */
function App() {
  const [tab, setTab]         = useState('about')
  const [animKey, setAnimKey] = useState(0)

  const handleNav = (id) => {
    setTab(id)
    setAnimKey(k => k + 1)
  }

  const sections = {
    about:      <AboutSection />,
    experience: <ExperienceSection />,
    projects:   <ProjectsSection />,
    feed:       <FeedSection />,
    contacts:   <ContactsSection />,
  }

  return (
    <div className="page">
      <div className="glow glow-1" />
      <div className="glow glow-2" />

      <main className="container">
        {/* ── Hero ── */}
        <header className="hero-section">
          <Avatar />
          <h1 className="hero-name">{BIO.fullName}</h1>
          <p className="hero-tagline">{BIO.tagline}</p>
          <div className="hero-meta">
            <span>{ICONS.location} {BIO.location}</span>
            <span>{ICONS.briefcase} {BIO.experience}</span>
          </div>
        </header>

        {/* ── Nav ── */}
        <Nav active={tab} onNav={handleNav} />

        {/* ── Content ── */}
        <div className="content-area" key={animKey}>
          {sections[tab]}
        </div>

        {/* ── Footer ── */}
        <footer className="footer" role="contentinfo">
          <span>© {new Date().getFullYear()} {BIO.name}</span>
          <a
            href={BIO.contacts.telegramLink}
            target="_blank"
            rel="noopener noreferrer"
            id="footer-telegram"
          >
            Telegram
          </a>
          <a href={`mailto:${BIO.contacts.email}`} id="footer-email">Email</a>
        </footer>
      </main>
    </div>
  )
}

export default App
