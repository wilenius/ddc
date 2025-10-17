(function () {
  // Configuration
  const MATCH_DURATION_MINUTES = 30;

  function buildSingleMatchGoogleLink(dateStr, timeStr, summary) {
    const dateBasic = dateStr.replace(/-/g, '');
    const safeSummary = encodeURIComponent(summary);

    if (!timeStr) {
      // All day event
      return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${safeSummary}&dates=${dateBasic}/${dateBasic}&details=${safeSummary}`;
    }

    const [hh, mm] = timeStr.split(':');
    const startDate = new Date(dateStr + 'T' + hh + ':' + mm + ':00');
    const endDate = new Date(
      startDate.getTime() + MATCH_DURATION_MINUTES * 60000
    );
    const startStr = dateBasic + 'T' + hh + mm + '00';
    const ehh = String(endDate.getHours()).padStart(2, '0');
    const emm = String(endDate.getMinutes()).padStart(2, '0');
    const endStr = dateBasic + 'T' + ehh + emm + '00';

    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${safeSummary}&dates=${startStr}/${endStr}&details=${safeSummary}`;
  }

  function buildSingleMatchOutlookComLink(dateStr, timeStr, summary) {
    const safeSummary = encodeURIComponent(summary);

    if (!timeStr) {
      return `https://outlook.live.com/calendar/0/action/compose?rru=addevent&subject=${safeSummary}&body=${safeSummary}&startdt=${dateStr}T00:00:00&enddt=${dateStr}T23:59:59`;
    }

    const [hh, mm] = timeStr.split(':');
    const startDate = new Date(dateStr + 'T' + hh + ':' + mm + ':00');
    const endDate = new Date(
      startDate.getTime() + MATCH_DURATION_MINUTES * 60000
    );
    const ehh = String(endDate.getHours()).padStart(2, '0');
    const emm = String(endDate.getMinutes()).padStart(2, '0');

    return `https://outlook.live.com/calendar/0/action/compose?rru=addevent&subject=${safeSummary}&body=${safeSummary}&startdt=${dateStr}T${hh}:${mm}:00&enddt=${dateStr}T${ehh}:${emm}:00`;
  }

  function generateSingleMatchICS(dateStr, timeStr, summary, tournamentName) {
    const now = new Date();
    const dtStamp = now
      .toISOString()
      .replace(/[-:]/g, '')
      .replace(/\.\d{3}Z$/, 'Z');
    const uid =
      'single-' + dateStr + '-' + Math.random().toString(36).slice(2) + '@ddc';

    let ics =
      'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//DDC Tournament Manager//EN\nBEGIN:VEVENT\n';
    ics += 'UID:' + uid + '\n';
    ics += 'DTSTAMP:' + dtStamp + '\n';

    if (timeStr) {
      const [hh, mm] = timeStr.split(':');
      const startDateObj = new Date(dateStr + 'T' + hh + ':' + mm + ':00');
      const endDateObj = new Date(
        startDateObj.getTime() + MATCH_DURATION_MINUTES * 60000
      );
      const ehh = String(endDateObj.getHours()).padStart(2, '0');
      const emm = String(endDateObj.getMinutes()).padStart(2, '0');
      const dtStart = dateStr.replace(/-/g, '') + 'T' + hh + mm + '00';
      const dtEnd = dateStr.replace(/-/g, '') + 'T' + ehh + emm + '00';
      ics += 'DTSTART:' + dtStart + '\n';
      ics += 'DTEND:' + dtEnd + '\n';
    } else {
      const dtAll = dateStr.replace(/-/g, '');
      ics += 'DTSTART;VALUE=DATE:' + dtAll + '\n';
      ics += 'DTEND;VALUE=DATE:' + dtAll + '\n';
    }

    const cleanSummary = summary.replace(/,/g, '');
    ics += 'SUMMARY:' + cleanSummary + '\n';
    ics +=
      'DESCRIPTION:' +
      tournamentName.replace(/,/g, '') +
      ' - ' +
      cleanSummary +
      '\n';
    ics += 'END:VEVENT\nEND:VCALENDAR';

    return ics;
  }

  function initPerMatchCalendars() {
    const tournamentNameEl = document.querySelector('h2');
    const tournamentName = tournamentNameEl
      ? tournamentNameEl.textContent.trim()
      : 'Tournament';

    document.querySelectorAll('.add-match-calendar').forEach((trigger) => {
      trigger.addEventListener('click', function (e) {
        e.preventDefault();
        const container = this.closest('.match-calendar-container');
        if (!container) return;

        const popup = container.querySelector('.match-calendar-popup');
        if (!popup) return;

        // Close any other open popups
        document.querySelectorAll('.match-calendar-popup').forEach((p) => {
          if (p !== popup) p.classList.add('d-none');
        });

        popup.classList.toggle('d-none');

        if (!popup.classList.contains('d-none')) {
          buildSingleMatchLinks(container, popup, tournamentName);
        }
      });
    });

    document.querySelectorAll('.close-match-popup').forEach((btn) => {
      btn.addEventListener('click', function () {
        const popup = this.closest('.match-calendar-popup');
        if (popup) popup.classList.add('d-none');
      });
    });

    document.querySelectorAll('.match-ics-link').forEach((link) => {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        const popup = this.closest('.match-calendar-popup');
        const container = popup
          ? popup.closest('.match-calendar-container')
          : null;
        if (!container) return;

        const dateStr = container.dataset.date;
        const timeStr = container.dataset.time || null;
        const summary = container.dataset.summary || 'Match';
        const ics = generateSingleMatchICS(
          dateStr,
          timeStr,
          summary,
          tournamentName
        );
        const filename =
          summary.replace(/\s+/g, '_').toLowerCase().slice(0, 40) +
          '_' +
          dateStr +
          '.ics';

        const blob = new Blob([ics], { type: 'text/calendar' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
    });

    // Close popups when clicking outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.match-calendar-container')) {
        document.querySelectorAll('.match-calendar-popup').forEach((popup) => {
          popup.classList.add('d-none');
        });
      }
    });
  }

  function buildSingleMatchLinks(container, popup, tournamentName) {
    const optionsDiv = popup.querySelector('.match-calendar-options');
    if (!optionsDiv || optionsDiv.getAttribute('data-init') === '1') return;

    const dateStr = container.dataset.date;
    const timeStr = container.dataset.time || null;
    const summaryRaw = container.dataset.summary || 'Match';
    const summary = tournamentName + ' - ' + summaryRaw;

    const gc = popup.querySelector('.match-gc-link');
    if (gc) {
      gc.href = buildSingleMatchGoogleLink(dateStr, timeStr, summary);
      gc.target = '_blank';
      gc.rel = 'noopener';
    }

    const outlook = popup.querySelector('.match-outlook-link');
    if (outlook) {
      outlook.href = buildSingleMatchOutlookComLink(dateStr, timeStr, summary);
      outlook.target = '_blank';
      outlook.rel = 'noopener';
    }

    optionsDiv.setAttribute('data-init', '1');
  }

  // Initialize when DOM is ready
  if (
    document.readyState === 'complete' ||
    document.readyState === 'interactive'
  ) {
    setTimeout(initPerMatchCalendars, 0);
  } else {
    document.addEventListener('DOMContentLoaded', initPerMatchCalendars);
  }

  // Expose minimal API if needed elsewhere
  window.CalendarMatchDay = {
    init: initPerMatchCalendars,
  };
})();
