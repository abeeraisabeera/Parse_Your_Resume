"use client";

import { useState } from "react";

import { removeRole, saveRole } from "../../lib/taxonomyApi";

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

export function RoleCategories({ workspace }) {
  const { roles, setRoles } = workspace;
  const [roleDraft, setRoleDraft] = useState(EMPTY_ROLE);
  const [message, setMessage] = useState("");

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
          <p className="eyebrow">Role Categories</p>
          <h2>Manage recruiter-defined role segments.</h2>
          <p className="subtle">Roles remain separate from skill taxonomy while still powering candidate filters.</p>
        </div>
      </section>

      {message ? <div className="message info">{message}</div> : null}

      <section className="twoColumnGrid alignStart">
        <article className="panel">
          <div className="panelHeader">
            <h2>{roleDraft.id ? "Edit Role" : "Add Role"}</h2>
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
