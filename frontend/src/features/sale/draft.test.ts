import { afterEach, describe, expect, it, vi } from "vitest";
import { clearDrafts } from "@/auth/session";
import { clearDraft, DRAFT_KEY, emptyDraft, loadDraft, saveDraft } from "./draft";

describe("sale draft", () => {
  afterEach(() => sessionStorage.clear());

  it("saves to and loads from sessionStorage under gj.draft.sale", () => {
    const draft = { ...emptyDraft(), gstin: "24ABCDE1234F1Z5", step: 1 };
    saveDraft(draft);
    expect(sessionStorage.getItem(DRAFT_KEY)).not.toBeNull();
    expect(DRAFT_KEY).toBe("gj.draft.sale");
    expect(loadDraft()).toEqual(draft);
  });

  it("returns null for no draft or a damaged one", () => {
    expect(loadDraft()).toBeNull();
    sessionStorage.setItem(DRAFT_KEY, "{not json");
    expect(loadDraft()).toBeNull();
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ step: "two" }));
    expect(loadDraft()).toBeNull();
  });

  it("is removed by clearDraft and by the sign-out clearDrafts", () => {
    saveDraft(emptyDraft());
    clearDraft();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    saveDraft(emptyDraft());
    clearDrafts();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("writes only to sessionStorage, never localStorage", () => {
    // jsdom's Storage methods live on the prototype, shared by both storages: every call's
    // `this` must be sessionStorage.
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    saveDraft(emptyDraft());
    loadDraft();
    clearDraft();
    expect(setItem).toHaveBeenCalled();
    expect(setItem.mock.contexts.every((storage) => storage === window.sessionStorage)).toBe(true);
  });
});
