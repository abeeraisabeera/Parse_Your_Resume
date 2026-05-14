"use client";

import { useMemo, useState } from "react";

import { ROLE_DEFINITIONS } from "../../lib/constants";
import { removeRole, removeSkill, saveRole, saveSkill } from "../../lib/taxonomyApi";

const EMPTY_SKILL = {
  id: "",
  label: "",
  category: "",
  aliases: "",
  roles: []
};

const EMPTY_ROLE = {
  id: "",
  label: "",
  short_label: "",
  category: "Custom",
  description: ""
};

function slugify(value) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function SkillsManagement({ workspace }) {
  const { skills, setSkills, roles, setRoles } = workspace;
  const [draft, setDraft] = useState(EMPTY_SKILL);
  const [roleDraft, setRoleDraft] = useState(EMPTY_ROLE);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");

  const filteredSkills = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return skills;
    return skills.filter((skill) =>
      [skill.id, skill.label, skill.category, ...(skill.aliases || []), ...(skill.roles || [])]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [skills, query]);

  function updateDraft(key, value) {
    setDraft((current) => ({
      ...current,
      [key]: value,
      id: key === "label" && !current.id ? slugify(value) : current.id
    }));
  }

  function toggleRole(roleId) {
    setDraft((current) => {
      const roles = new Set(current.roles);
      if (roles.has(roleId)) roles.delete(roleId);
      else roles.add(roleId);
      return { ...current, roles: [...roles] };
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const id = draft.id || slugify(draft.label);
    if (!id || !draft.label.trim()) {
      setMessage("Skill name is required.");
      return;
    }

    const duplicate = skills.find((skill) => skill.id === id && skill.id !== draft.originalId);
    if (duplicate) {
      setMessage("A skill with this name already exists.");
      return;
    }

    const payload = {
      id,
      label: draft.label.trim(),
      category: draft.category.trim() || "Uncategorized",
      aliases: draft.aliases
        .split(/[,;]/)
        .map((alias) => alias.trim())
        .filter(Boolean),
      roles: draft.roles
    };

    try {
      const saved = await saveSkill(payload);
      setSkills((current) => [saved, ...current.filter((skill) => skill.id !== saved.id)]);
      setDraft(EMPTY_SKILL);
      setMessage("Skill saved and available for filtering.");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function handleDelete(skillId) {
    try {
      await removeSkill(skillId);
      setSkills((current) => current.filter((skill) => skill.id !== skillId));
      setMessage("Skill deleted.");
    } catch (error) {
      setMessage(error.message);
    }
  }

  function editSkill(skill) {
    setDraft({
      id: skill.id,
      originalId: skill.id,
      label: skill.label || skill.name || skill.id,
      category: skill.category || "",
      aliases: (skill.aliases || []).join(", "),
      roles: skill.roles || []
    });
  }

  function updateRoleDraft(key, value) {
    setRoleDraft((current) => ({
      ...current,
      [key]: value,
      id: key === "label" && !current.id ? slugify(value) : current.id
    }));
  }

  async function handleRoleSubmit(event) {
    event.preventDefault();
    const id = roleDraft.id || slugify(roleDraft.label);
    if (!id || !roleDraft.label.trim()) {
      setMessage("Role name is required.");
      return;
    }
    try {
      const saved = await saveRole({
        ...roleDraft,
        id,
        label: roleDraft.label.trim(),
        is_custom: true
      });
      setRoles((current) => [saved, ...current.filter((role) => role.id !== saved.id)]);
      setRoleDraft(EMPTY_ROLE);
      setMessage("Role saved for future candidate segmentation.");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function handleRoleDelete(roleId) {
    try {
      await removeRole(roleId);
      setRoles((current) => current.filter((role) => role.id !== roleId));
      setMessage("Custom role deleted.");
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Skills Management</p>
          <h2>Maintain a recruiter-controlled skills taxonomy.</h2>
          <p className="subtle">Managed skills map to roles and feed the reusable filter dropdowns.</p>
        </div>
      </section>

      {message ? <div className="message info">{message}</div> : null}

      <section className="twoColumnGrid alignStart">
        <article className="panel">
          <div className="panelHeader">
            <h2>{draft.originalId ? "Edit Skill" : "Add Skill"}</h2>
            <button className="textButton" type="button" onClick={() => setDraft(EMPTY_SKILL)}>Clear</button>
          </div>

          <form className="form" onSubmit={handleSubmit}>
            <label className="label">
              Skill name
              <input
                className="input"
                value={draft.label}
                onChange={(event) => updateDraft("label", event.target.value)}
                placeholder="React, PyTorch, Figma"
              />
            </label>
            <label className="label">
              Skill ID
              <input
                className="input"
                value={draft.id}
                onChange={(event) => updateDraft("id", slugify(event.target.value))}
                placeholder="react"
              />
            </label>
            <label className="label">
              Category
              <input
                className="input"
                value={draft.category}
                onChange={(event) => updateDraft("category", event.target.value)}
                placeholder="Frontend, ML/AI, UI/UX"
              />
            </label>
            <label className="label">
              Aliases
              <input
                className="input"
                value={draft.aliases}
                onChange={(event) => updateDraft("aliases", event.target.value)}
                placeholder="Comma separated"
              />
            </label>

            <div className="rolePicker">
              <span className="summaryLabel">Map to roles</span>
              {ROLE_DEFINITIONS.filter((role) => role.id !== "all").map((role) => (
                <label className="checkboxRow compactCheck" key={role.id}>
                  <input
                    type="checkbox"
                    checked={draft.roles.includes(role.id)}
                    onChange={() => toggleRole(role.id)}
                  />
                  <span>{role.label}</span>
                </label>
              ))}
            </div>

            <button className="button" type="submit">Save Skill</button>
          </form>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <div>
              <h2>Managed Skills</h2>
              <p className="subtle">{filteredSkills.length} skill(s)</p>
            </div>
            <label className="searchBox inlineSearch">
              <span>Search</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find skill" />
            </label>
          </div>

          <div className="skillList">
            {filteredSkills.map((skill) => (
              <div className="skillRow" key={skill.id}>
                <span>
                  <strong>{skill.label || skill.name || skill.id}</strong>
                  <small>{skill.category || "Uncategorized"} - {(skill.roles || []).join(", ") || "No role mapping"}</small>
                </span>
                <div className="tableActions">
                  <button className="secondaryButton" type="button" onClick={() => editSkill(skill)}>Edit</button>
                  <button className="dangerButton" type="button" onClick={() => handleDelete(skill.id)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="twoColumnGrid alignStart">
        <article className="panel">
          <div className="panelHeader">
            <h2>Role Categories</h2>
            <button className="textButton" type="button" onClick={() => setRoleDraft(EMPTY_ROLE)}>Clear</button>
          </div>
          <form className="form" onSubmit={handleRoleSubmit}>
            <label className="label">
              Role label
              <input
                className="input"
                value={roleDraft.label}
                onChange={(event) => updateRoleDraft("label", event.target.value)}
                placeholder="ML Engineer, Product Manager"
              />
            </label>
            <label className="label">
              Role ID
              <input
                className="input"
                value={roleDraft.id}
                onChange={(event) => updateRoleDraft("id", slugify(event.target.value))}
                placeholder="ml-engineer"
              />
            </label>
            <label className="label">
              Category
              <input
                className="input"
                value={roleDraft.category}
                onChange={(event) => updateRoleDraft("category", event.target.value)}
                placeholder="Engineering, Revenue"
              />
            </label>
            <label className="label">
              Description
              <input
                className="input"
                value={roleDraft.description}
                onChange={(event) => updateRoleDraft("description", event.target.value)}
                placeholder="Optional recruiter-facing description"
              />
            </label>
            <button className="button" type="submit">Save Role</button>
          </form>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Available Roles</h2>
            <span>{roles.length}</span>
          </div>
          <div className="skillList">
            {roles.map((role) => (
              <div className="skillRow" key={role.id}>
                <span>
                  <strong>{role.label}</strong>
                  <small>{role.category || "Custom"} - {role.is_custom ? "custom" : "default"}</small>
                </span>
                <div className="tableActions">
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={() => setRoleDraft({
                      id: role.id,
                      label: role.label,
                      short_label: role.short_label || role.shortLabel || "",
                      category: role.category || "",
                      description: role.description || ""
                    })}
                  >
                    Edit
                  </button>
                  <button
                    className="dangerButton"
                    type="button"
                    disabled={!role.is_custom}
                    onClick={() => handleRoleDelete(role.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
