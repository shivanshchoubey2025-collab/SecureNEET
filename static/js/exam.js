/* ==========================================================================
   SecureNEET — Examination Interface Client Controller
   Synchronized Server Timer, Question Navigation, Palette State & Autosave
   ========================================================================== */

class ExamController {
  constructor(config) {
    this.attemptId = config.attemptId;
    this.remainingSeconds = config.remainingSeconds;
    this.questions = config.questions;
    this.savedAnswers = config.savedAnswers || {};
    this.currentIndex = 0;
    this.currentSubject = 'Physics';
    this.visitedQuestions = new Set();

    this.timerInterval = null;
    this.syncInterval = null;

    this.init();
  }

  init() {
    this.initTimer();
    this.renderSubjectTabs();
    this.renderPalette();
    this.loadQuestion(0);
    this.attachEventListeners();
  }

  /* ---------------- TIMER MANAGEMENT ---------------- */
  initTimer() {
    this.updateTimerDisplay();
    this.timerInterval = setInterval(() => {
      this.remainingSeconds--;
      this.updateTimerDisplay();

      if (this.remainingSeconds <= 0) {
        clearInterval(this.timerInterval);
        this.autoSubmitExam("Examination time has elapsed. Your answers are being submitted.");
      }
    }, 1000);

    // Sync timer with server every 45 seconds to prevent client clock drift
    this.syncInterval = setInterval(() => this.syncServerTimer(), 45000);
  }

  syncServerTimer() {
    fetch(`/exam/api/attempt/${this.attemptId}/time`)
      .then(r => r.json())
      .then(data => {
        if (data.status === 'expired') {
          this.autoSubmitExam("Server session expired.");
        } else if (typeof data.remaining_seconds === 'number') {
          this.remainingSeconds = data.remaining_seconds;
          this.updateTimerDisplay();
        }
      })
      .catch(err => console.warn("Timer sync failed:", err));
  }

  updateTimerDisplay() {
    const el = document.getElementById('examTimer');
    if (!el) return;

    const s = Math.max(0, this.remainingSeconds);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;

    const formatted = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    el.textContent = formatted;

    if (this.remainingSeconds <= 300) {
      el.parentElement.classList.add('timer-warning');
    }
  }

  /* ---------------- QUESTION NAVIGATION ---------------- */
  loadQuestion(index) {
    if (index < 0 || index >= this.questions.length) return;
    this.currentIndex = index;
    const q = this.questions[index];
    this.visitedQuestions.add(q.id);

    // Update subject tab if different
    if (q.subject !== this.currentSubject) {
      this.currentSubject = q.subject;
      this.updateSubjectTabsUI();
    }

    // Question header & text
    document.getElementById('currentQNum').textContent = `Question ${index + 1} of ${this.questions.length}`;
    document.getElementById('currentSubjectBadge').textContent = `${q.subject} • ${q.topic || 'General'}`;
    document.getElementById('questionText').textContent = q.question_text;
    document.getElementById('marksBadge').textContent = `+${q.marks} / -${q.negative_marks}`;

    // Options rendering
    const optContainer = document.getElementById('optionsContainer');
    optContainer.innerHTML = '';

    const saved = this.savedAnswers[q.id];
    const selectedOpt = saved ? saved.selected_option : null;

    const opts = [
      { key: 'A', text: q.option_a },
      { key: 'B', text: q.option_b },
      { key: 'C', text: q.option_c },
      { key: 'D', text: q.option_d }
    ];

    opts.forEach(opt => {
      const item = document.createElement('label');
      item.className = `option-item ${selectedOpt === opt.key ? 'selected' : ''}`;
      item.innerHTML = `
        <input type="radio" name="optRadio" value="${opt.key}" class="option-radio" ${selectedOpt === opt.key ? 'checked' : ''}>
        <span class="option-label">(${opt.key})</span>
        <span class="option-text">${this.escapeHTML(opt.text)}</span>
      `;
      item.addEventListener('click', () => {
        document.querySelectorAll('.option-item').forEach(i => i.classList.remove('selected'));
        item.classList.add('selected');
        const radio = item.querySelector('input[type="radio"]');
        radio.checked = true;
      });
      optContainer.appendChild(item);
    });

    this.updatePaletteButtonHighlight();
  }

  escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }

  getSelectedOption() {
    const checked = document.querySelector('input[name="optRadio"]:checked');
    return checked ? checked.value : null;
  }

  /* ---------------- SAVE & ACTIONS ---------------- */
  saveAndNext(isMarkForReview = false) {
    const q = this.questions[this.currentIndex];
    const selected = this.getSelectedOption();

    // Update local state
    if (!this.savedAnswers[q.id]) {
      this.savedAnswers[q.id] = {};
    }
    this.savedAnswers[q.id].selected_option = selected;
    this.savedAnswers[q.id].is_marked_for_review = isMarkForReview;

    // Dispatch background save to server
    this.postAnswer(q.id, selected, isMarkForReview);

    this.updatePaletteButtonStatus(this.currentIndex);

    // Jump to next question if available
    if (this.currentIndex < this.questions.length - 1) {
      this.loadQuestion(this.currentIndex + 1);
    }
  }

  clearResponse() {
    const q = this.questions[this.currentIndex];
    document.querySelectorAll('.option-item').forEach(i => i.classList.remove('selected'));
    const checked = document.querySelector('input[name="optRadio"]:checked');
    if (checked) checked.checked = false;

    if (this.savedAnswers[q.id]) {
      this.savedAnswers[q.id].selected_option = null;
      this.savedAnswers[q.id].is_marked_for_review = false;
    }

    this.postAnswer(q.id, null, false);
    this.updatePaletteButtonStatus(this.currentIndex);
  }

  postAnswer(questionId, selectedOption, isMarkedForReview) {
    fetch(`/exam/api/attempt/${this.attemptId}/save-answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: questionId,
        selected_option: selectedOption,
        is_marked_for_review: isMarkedForReview
      })
    })
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        console.warn("Autosave warning:", data.error);
      }
    })
    .catch(err => console.error("Autosave network error:", err));
  }

  /* ---------------- PALETTE & SUBJECTS ---------------- */
  renderSubjectTabs() {
    const nav = document.getElementById('subjectNav');
    if (!nav) return;

    const subjects = ['Physics', 'Chemistry', 'Botany', 'Zoology'];
    nav.innerHTML = '';

    subjects.forEach(subj => {
      const btn = document.createElement('button');
      btn.className = `subject-tab ${subj === this.currentSubject ? 'active' : ''}`;
      btn.textContent = subj;
      btn.addEventListener('click', () => {
        this.currentSubject = subj;
        this.updateSubjectTabsUI();
        // Jump to first question of this subject
        const idx = this.questions.findIndex(q => q.subject === subj);
        if (idx !== -1) {
          this.loadQuestion(idx);
        }
      });
      nav.appendChild(btn);
    });
  }

  updateSubjectTabsUI() {
    document.querySelectorAll('.subject-tab').forEach(t => {
      t.classList.toggle('active', t.textContent === this.currentSubject);
    });
  }

  renderPalette() {
    const grid = document.getElementById('paletteGrid');
    if (!grid) return;
    grid.innerHTML = '';

    this.questions.forEach((q, idx) => {
      const btn = document.createElement('button');
      btn.id = `palette-btn-${idx}`;
      btn.className = `palette-btn ${this.getQuestionStatusClass(idx)}`;
      btn.textContent = idx + 1;
      btn.addEventListener('click', () => this.loadQuestion(idx));
      grid.appendChild(btn);
    });
  }

  getQuestionStatusClass(idx) {
    const q = this.questions[idx];
    const saved = this.savedAnswers[q.id];
    const hasAnswer = saved && saved.selected_option;
    const isMarked = saved && saved.is_marked_for_review;

    if (hasAnswer && isMarked) return 'status-marked-answered';
    if (isMarked) return 'status-marked';
    if (hasAnswer) return 'status-answered';
    if (this.visitedQuestions.has(q.id)) return 'status-not-answered';
    return 'status-not-visited';
  }

  updatePaletteButtonStatus(idx) {
    const btn = document.getElementById(`palette-btn-${idx}`);
    if (btn) {
      btn.className = `palette-btn ${this.getQuestionStatusClass(idx)} ${idx === this.currentIndex ? 'current' : ''}`;
    }
  }

  updatePaletteButtonHighlight() {
    this.questions.forEach((_, idx) => {
      this.updatePaletteButtonStatus(idx);
    });
  }

  /* ---------------- SUBMISSION MODAL ---------------- */
  showSubmitModal() {
    let answered = 0;
    let notAnswered = 0;
    let marked = 0;
    let notVisited = 0;

    this.questions.forEach(q => {
      const saved = this.savedAnswers[q.id];
      const hasAns = saved && saved.selected_option;
      const isMrk = saved && saved.is_marked_for_review;

      if (hasAns) answered++;
      else if (this.visitedQuestions.has(q.id)) notAnswered++;
      else notVisited++;

      if (isMrk) marked++;
    });

    document.getElementById('statAnsweredCount').textContent = answered;
    document.getElementById('statNotAnsweredCount').textContent = notAnswered;
    document.getElementById('statMarkedCount').textContent = marked;
    document.getElementById('statNotVisitedCount').textContent = notVisited;

    document.getElementById('submitModal').style.display = 'flex';
  }

  closeSubmitModal() {
    document.getElementById('submitModal').style.display = 'none';
  }

  autoSubmitExam(msg) {
    alert(msg);
    document.getElementById('finalSubmitForm').submit();
  }

  attachEventListeners() {
    document.getElementById('btnSaveNext').addEventListener('click', () => this.saveAndNext(false));
    document.getElementById('btnMarkReview').addEventListener('click', () => this.saveAndNext(true));
    document.getElementById('btnClearResponse').addEventListener('click', () => this.clearResponse());
    document.getElementById('btnPrev').addEventListener('click', () => {
      if (this.currentIndex > 0) this.loadQuestion(this.currentIndex - 1);
    });
    document.getElementById('btnOpenSubmit').addEventListener('click', () => this.showSubmitModal());
    document.getElementById('btnCloseModal').addEventListener('click', () => this.closeSubmitModal());
  }
}

window.ExamController = ExamController;
