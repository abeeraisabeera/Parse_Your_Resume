import { CandidateFilters } from "./CandidateFilters";

export function FiltersWorkspace({ workspace }) {
  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Filters</p>
          <h2>Centralized reusable candidate filtering.</h2>
          <p className="subtle">These controls use the same state as Candidates, Dashboard, Analytics, and Export.</p>
        </div>
      </section>

      <CandidateFilters
        filters={workspace.filters}
        setFilter={workspace.setFilter}
        clearFilters={workspace.clearFilters}
        activeFilterChips={workspace.activeFilterChips}
        removeFilter={workspace.removeFilter}
        skills={workspace.skills}
        roles={workspace.roles}
      />

      <section className="panel">
        <div className="panelHeader">
          <h2>Saved Filter Foundation</h2>
          <span>Coming next</span>
        </div>
        <p className="subtle">
          The global filter state is now reusable and URL-persistent. This page is ready for saved recruiter presets such as
          “Senior Frontend 80+”, “ML Candidates”, or “Needs Review”.
        </p>
      </section>
    </div>
  );
}
