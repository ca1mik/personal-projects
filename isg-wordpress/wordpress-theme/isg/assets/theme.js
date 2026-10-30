document.addEventListener('DOMContentLoaded', () => {
  const menuButton = document.querySelector('[data-menu-toggle]');
  const mobileNavigation = document.querySelector('#mobile-navigation');
  menuButton?.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(open));
    mobileNavigation.hidden = !open;
  });

  const search = document.querySelector('[data-search-overlay]');
  const closeSearch = () => { search.hidden = true; document.querySelector('[data-search-open]')?.focus(); };
  document.querySelector('[data-search-open]')?.addEventListener('click', () => {
    search.hidden = false;
    search.querySelector('input[type="search"]')?.focus();
  });
  document.querySelector('[data-search-close]')?.addEventListener('click', closeSearch);
  search?.addEventListener('click', event => { if (event.target === search) closeSearch(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && search && !search.hidden) closeSearch();
  });

  const slider = document.querySelector('[data-slider]');
  if (slider) {
    const panels = [...slider.querySelectorAll('[data-slide-panel]')];
    const dots = [...slider.querySelectorAll('[data-slide-target]')];
    const show = index => {
      panels.forEach((panel, i) => { panel.hidden = i !== index; panel.classList.toggle('active', i === index); });
      panels.forEach((panel, i) => {
        const video = panel.querySelector('video');
        if (video) { if (i === index) video.play().catch(() => {}); else video.pause(); }
      });
      dots.forEach((dot, i) => { dot.classList.toggle('active', i === index); dot.setAttribute('aria-current', i === index ? 'true' : 'false'); });
    };
    dots.forEach(dot => dot.addEventListener('click', () => show(Number(dot.dataset.slideTarget))));
    if (panels.length > 1 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      let current = 0;
      window.setInterval(() => { if (!document.hidden) { current = (current + 1) % panels.length; show(current); } }, 8000);
    }
  }

  const content = document.querySelector('[data-detail-content]');
  const nav = document.querySelector('[data-detail-nav]');
  if (content && nav) {
    const headings = [...document.querySelectorAll('.entry-content h2, .detail-section h2')].slice(0, 10);
    headings.forEach((heading, index) => {
      if (!heading.id) heading.id = `section-${index + 1}`;
      const link = document.createElement('a');
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent.trim();
      nav.append(link);
    });
  }

  document.querySelectorAll('[data-case-carousel]').forEach(carousel => {
    const section = carousel.closest('section');
    const distance = () => carousel.clientWidth + 18;
    section.querySelector('[data-carousel-prev]')?.addEventListener('click', () => carousel.scrollBy({ left: -distance(), behavior: 'smooth' }));
    section.querySelector('[data-carousel-next]')?.addEventListener('click', () => carousel.scrollBy({ left: distance(), behavior: 'smooth' }));
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && carousel.children.length > 4) {
      window.setInterval(() => {
        if (document.hidden || carousel.matches(':hover')) return;
        const end = carousel.scrollLeft + carousel.clientWidth >= carousel.scrollWidth - 4;
        carousel.scrollTo({ left: end ? 0 : carousel.scrollLeft + distance(), behavior: 'smooth' });
      }, 8000);
    }
  });
});
