const paths = {
  words: <><path d="M12 6c-3-2-6-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Z" /><path d="M12 6v14" /></>,
  notebooks: <><rect x="6" y="3" width="14" height="17" rx="2" /><path d="M10 3v17M6 7H3v14h13M13 8h4M13 12h4" /></>,
  review: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 7a7.5 7.5 0 0 1 12.2-2L20 8M4 16l2.2 3A7.5 7.5 0 0 0 18.4 17" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  organize: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 16h7M14 20h7" /></>,
  download: <><path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5" /></>,
  collapse: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16m7-12-4 4 4 4" /></>,
  expand: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16m4-12 4 4-4 4" /></>,
  settings: <><path d="m9.5 3-.7 2.3-2 .9-2.2-.5-2 3.4 1.5 1.8v2.2L2.6 15l2 3.4 2.2-.5 2 .9.7 2.2h5l.7-2.2 2-.9 2.2.5 2-3.4-1.5-1.9v-2.2l1.5-1.8-2-3.4-2.2.5-2-.9-.7-2.3Z" /><circle cx="12" cy="12" r="3" /></>,
  model: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" /></>,
  cloud: <><path d="M7 18a5 5 0 0 1-.7-9.95A6 6 0 0 1 18 7a5.5 5.5 0 0 1 .5 11H7Z" /><path d="m9 13 3-3 3 3m-3-3v10" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5" /></>,
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />,
  keyboard: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M7 16h10" /></>,
  chevron: <path d="m8 10 4 4 4-4" />,
  arrow: <path d="m9 6 6 6-6 6" />,
}

export default function NavigationIcon({ name, className = '' }) {
  return <svg className={`navigation-icon ${className}`} width="20" height="20" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {paths[name]}
  </svg>
}
