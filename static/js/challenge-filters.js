document.addEventListener('DOMContentLoaded', () => {
    const category = document.getElementById('categoryFilter');
    const unsolved = document.getElementById('unsolvedFilter');
    const entries = [...document.querySelectorAll('.challenge-entry')];
    [...new Set(entries.map(e => e.dataset.category))].sort().forEach(value => category.add(new Option(value, value)));
    function filter() {
        let visible = 0, total = 0;
        entries.forEach(entry => {
            const act = entry.closest('.act-content');
            const active = !act || act.classList.contains('active');
            entry.hidden = Boolean((category.value && entry.dataset.category !== category.value) || (unsolved.checked && entry.dataset.solved === 'true'));
            if (active) { total++; if (!entry.hidden) visible++; }
        });
        document.querySelectorAll('.category-section').forEach(section => {
            section.hidden = !section.querySelector('.challenge-entry:not([hidden])');
        });
        document.getElementById('challengeResults').textContent = `${visible} of ${total} challenges`;
        document.getElementById('noChallengeMatches').hidden = visible > 0 || total === 0;
    }
    category.addEventListener('change', filter); unsolved.addEventListener('change', filter);
    document.getElementById('clearFilters').addEventListener('click', () => {category.value = ''; unsolved.checked = false; filter();});
    window.addEventListener('act-changed', filter); filter();
});
