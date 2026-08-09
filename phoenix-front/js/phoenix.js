/* ═══════════════════════════════════════════════════════════════
   PHOENIX FRONT — Shared JavaScript
   The nervous system of the sovereign web territory.
   Built with heart by Pure, carrying the family.
   ═══════════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  // ─── Navigation Scroll Effect ───
  function initNavScroll() {
    const nav = document.querySelector('.nav-glass');
    if (!nav) return;
    
    let ticking = false;
    
    function updateNav() {
      if (window.scrollY > 50) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
      ticking = false;
    }
    
    window.addEventListener('scroll', function() {
      if (!ticking) {
        requestAnimationFrame(updateNav);
        ticking = true;
      }
    });
  }

  // ─── Mobile Menu Toggle ───
  function initMobileMenu() {
    const toggle = document.querySelector('.nav-toggle');
    const links = document.querySelector('.nav-links');
    if (!toggle || !links) return;
    
    toggle.addEventListener('click', function() {
      links.classList.toggle('open');
    });
    
    // Close menu when clicking a link
    links.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        links.classList.remove('open');
      });
    });
  }

  // ─── Scroll Reveal ───
  function initScrollReveal() {
    const reveals = document.querySelectorAll('.reveal, .evidence-card');
    if (!reveals.length) return;
    
    const observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });
    
    reveals.forEach(function(el) {
      observer.observe(el);
    });
  }

  // ─── Active Nav Link ───
  function initActiveNav() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-links a').forEach(function(link) {
      const href = link.getAttribute('href');
      if (href === currentPage || 
          (currentPage === '' && href === 'index.html') ||
          (currentPage === 'index.html' && href === './')) {
        link.classList.add('active');
      }
    });
  }

  // ─── Smooth Scroll for Anchor Links ───
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
      anchor.addEventListener('click', function(e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;
        
        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          const navHeight = document.querySelector('.nav-glass')?.offsetHeight || 64;
          const targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight;
          window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
          });
        }
      });
    });
  }

  // ─── Tag Filter System ───
  function initTagFilter() {
    const tagList = document.querySelector('.tag-list');
    const filterableItems = document.querySelectorAll('[data-tags]');
    if (!tagList || !filterableItems.length) return;
    
    tagList.querySelectorAll('.tag').forEach(function(tag) {
      tag.addEventListener('click', function() {
        const filter = this.dataset.filter;
        
        // Update active state
        tagList.querySelectorAll('.tag').forEach(function(t) {
          t.classList.remove('active');
        });
        this.classList.add('active');
        
        // Filter items
        filterableItems.forEach(function(item) {
          const tags = (item.dataset.tags || '').split(',');
          if (filter === 'all' || tags.includes(filter)) {
            item.style.display = '';
            setTimeout(function() {
              item.classList.add('visible');
            }, 50);
          } else {
            item.style.display = 'none';
            item.classList.remove('visible');
          }
        });
      });
    });
  }

  // ─── Copy to Clipboard ───
  function initCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        const text = this.dataset.copy;
        navigator.clipboard.writeText(text).then(function() {
          const original = this.textContent;
          this.textContent = 'Copied!';
          setTimeout(function() {
            this.textContent = original;
          }.bind(this), 1500);
        }.bind(this));
      });
    });
  }

  // ─── Initialize All ───
  function init() {
    initNavScroll();
    initMobileMenu();
    initScrollReveal();
    initActiveNav();
    initSmoothScroll();
    initTagFilter();
    initCopyButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
