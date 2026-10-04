import { afterEach, describe, expect, it, vi } from "vitest";
import { clearDrafts } from "@/auth/session";
import { clearDraft, DRAFT_KEY, emptyDraft, loadDraft, saveDraft } from "./draft";

const OWNER = "GJK2PY48DX3B";

describe("sale draft", () => {
  afterEach(() => sessionStorage.clear());

  it("saves to and loads from sessionStorage under gj.draft.sale", () => {
    const draft = { ...emptyDraft(), gstin: "24ABCDE1234F1Z5", step: 1 };
    saveDraft(draft, OWNER);
    expect(sessionStorage.getItem(DRAFT_KEY)).not.toBeNull();
    expect(DRAFT_KEY).toBe("gj.draft.sale");
    expect(loadDraft(OWNER)).toEqual(draft);
  });

  it("returns null for no draft or a damaged one", () => {
    expect(loadDraft(OWNER)).toBeNull();
    sessionStorage.setItem(DRAFT_KEY, "{not json");
    expect(loadDraft(OWNER)).toBeNull();
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ step: "two" }));
    expect(loadDraft(OWNER)).toBeNull();
  });

  it("is removed by clearDraft and by the sign-out clearDrafts", () => {
    saveDraft(emptyDraft(), OWNER);
    clearDraft();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
    saveDraft(emptyDraft(), OWNER);
    clearDrafts();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("belongs to the user who wrote it: another user's draft is discarded, not restored", () => {
    saveDraft({ ...emptyDraft(), gstin: "24ABCDE1234F1Z5" }, "USER-A");
    expect(JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "{}")).toMatchObject({
      owner: "USER-A",
    });
    expect(loadDraft("USER-B")).toBeNull();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("discards a draft that names no owner", () => {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(emptyDraft()));
    expect(loadDraft(OWNER)).toBeNull();
    expect(sessionStorage.getItem(DRAFT_KEY)).toBeNull();
  });

  it("writes only to sessionStorage, never localStorage", () => {
    // jsdom's Storage methods live on the prototype, shared by both storages: every call's
    // `this` must be sessionStorage.
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    saveDraft(emptyDraft(), OWNER);
    loadDraft(OWNER);
    clearDraft();
    expect(setItem).toHaveBeenCalled();
    expect(setItem.mock.contexts.every((storage) => storage === window.sessionStorage)).toBe(true);
  });
});
