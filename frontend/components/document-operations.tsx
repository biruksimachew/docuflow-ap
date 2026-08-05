"use client";

import {
  FormEvent,
  useMemo,
  useState,
  useTransition,
} from "react";
import {
  useRouter,
} from "next/navigation";

import {
  StatusBadge,
} from "@/components/status-badge";
import {
  operationRequest,
} from "@/lib/client-api";
import {
  formatDateTime,
  humanize,
} from "@/lib/format";
import type {
  AccountingExport,
  AppRole,
  EffectiveInvoiceSnapshot,
  LineItem,
  NotificationDelivery,
  ReviewCorrection,
  ReviewSnapshot,
} from "@/lib/types";


const HEADER_FIELDS = [
  "vendor_name",
  "invoice_number",
  "invoice_date",
  "due_date",
  "purchase_order_number",
  "currency",
  "subtotal",
  "discount_amount",
  "shipping_amount",
  "tax_amount",
  "total_amount",
];

const LINE_FIELDS = [
  "description",
  "supplier_sku",
  "quantity",
  "unit_of_measure",
  "unit_price",
  "tax_rate",
  "line_total",
  "currency",
];


type Feedback = {
  kind: "success" | "error";
  message: string;
} | null;


type DocumentOperationsProps = {
  user: {
    user_id: string;
    email: string;
    role: AppRole;
  };
  documentId: string;
  documentStatus: string;
  lineItems: LineItem[];
  reviewSnapshot: ReviewSnapshot | null;
  effectiveInvoice: EffectiveInvoiceSnapshot | null;
  exports: AccountingExport[];
  notifications: NotificationDelivery[];
};


function displayValue(
  value: unknown,
): string {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  return typeof value === "object"
    ? JSON.stringify(value)
    : String(value);
}


function correctionLabel(
  correction: ReviewCorrection,
): string {
  const target =
    correction.target_type === "HEADER"
      ? "Header"
      : "Line item";

  return (
    `${target} · ` +
    humanize(correction.field_name)
  );
}


export function DocumentOperations({
  user,
  documentId,
  documentStatus,
  lineItems,
  reviewSnapshot,
  effectiveInvoice,
  exports,
  notifications,
}: DocumentOperationsProps) {
  const router = useRouter();

  const [
    pendingAction,
    setPendingAction,
  ] = useState<string | null>(null);

  const [
    feedback,
    setFeedback,
  ] = useState<Feedback>(null);

  const [
    correctionTarget,
    setCorrectionTarget,
  ] = useState<
    "HEADER" | "LINE_ITEM"
  >("HEADER");

  const [
    isRefreshing,
    startRefresh,
  ] = useTransition();

  const reviewCase =
    reviewSnapshot?.review_case ?? null;

  const activeCase = Boolean(
    reviewCase &&
    ["OPEN", "CLAIMED"].includes(
      reviewCase.status,
    ),
  );

  const reviewerRole =
    user.role === "REVIEWER" ||
    user.role === "ADMIN";

  const canManageClaimedCase =
    Boolean(
      reviewCase?.status === "CLAIMED" &&
      (
        user.role === "ADMIN" ||
        (
          user.role === "REVIEWER" &&
          reviewCase.claimed_by_user_id ===
            user.user_id
        )
      ),
    );

  const readyExports = useMemo(
    () =>
      exports.filter(
        (item) =>
          item.status === "READY",
      ),
    [exports],
  );

  async function perform<T>(
    actionName: string,
    path: string,
    body: unknown | undefined,
    successMessage: string,
  ): Promise<T | null> {
    setPendingAction(
      actionName,
    );
    setFeedback(null);

    try {
      const result =
        await operationRequest<T>(
          path,
          {
            method: "POST",
            body:
              body === undefined
                ? undefined
                : JSON.stringify(body),
          },
        );

      setFeedback({
        kind: "success",
        message: successMessage,
      });

      startRefresh(() => {
        router.refresh();
      });

      return result;
    } catch (error) {
      setFeedback({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "The operation failed.",
      });

      return null;
    } finally {
      setPendingAction(null);
    }
  }

  async function submitNote(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!reviewCase) {
      return;
    }

    const form = event.currentTarget;
    const data = new FormData(form);

    const result = await perform(
      "note",
      `reviews/${reviewCase.id}/notes`,
      {
        note: String(
          data.get("note") ?? "",
        ).trim(),
      },
      "Review note added.",
    );

    if (result) {
      form.reset();
    }
  }

  async function submitCorrection(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!reviewCase) {
      return;
    }

    const form = event.currentTarget;
    const data = new FormData(form);

    const targetType = String(
      data.get("target_type") ??
      "HEADER",
    ) as "HEADER" | "LINE_ITEM";

    const result = await perform<{
      correction: ReviewCorrection;
    }>(
      "correction",
      `reviews/${reviewCase.id}/corrections`,
      {
        target_type: targetType,
        line_item_id:
          targetType === "LINE_ITEM"
            ? String(
                data.get(
                  "line_item_id",
                ) ?? "",
              )
            : null,
        field_name: String(
          data.get("field_name") ?? "",
        ),
        corrected_value: String(
          data.get(
            "corrected_value",
          ) ?? "",
        ),
        reason: String(
          data.get("reason") ?? "",
        ),
        apply_immediately: false,
      },
      "Correction proposed.",
    );

    if (result) {
      form.reset();
      setCorrectionTarget(
        "HEADER",
      );
    }
  }

  async function submitResolution(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!reviewCase) {
      return;
    }

    const form = event.currentTarget;
    const data = new FormData(form);
    const resolution = String(
      data.get("resolution") ??
      "APPROVE",
    );

    const confirmed = window.confirm(
      resolution === "APPROVE"
        ? "Approve this invoice using the current reviewed values?"
        : "Reject this invoice and close the review case?",
    );

    if (!confirmed) {
      return;
    }

    const result = await perform(
      `resolve-${resolution}`,
      `reviews/${reviewCase.id}/resolve`,
      {
        resolution,
        note: String(
          data.get("note") ?? "",
        ),
      },
      resolution === "APPROVE"
        ? "Invoice approved."
        : "Invoice rejected.",
    );

    if (result) {
      form.reset();
    }
  }

  async function submitDelivery(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const form = event.currentTarget;
    const data = new FormData(form);
    const exportId = String(
      data.get("export_id") ?? "",
    );

    const result = await perform(
      "delivery",
      `exports/${exportId}/notifications`,
      {
        channel: String(
          data.get("channel") ??
          "EMAIL",
        ),
        destination: String(
          data.get("destination") ??
          "",
        ),
      },
      "Delivery queued.",
    );

    if (result) {
      form.reset();
    }
  }

  return (
    <section className="operations-workspace">
      <div className="operations-heading">
        <div>
          <div className="eyebrow">
            Interactive operations
          </div>
          <h2>
            Review, export and delivery controls
          </h2>
          <p>
            Every action is authorized by
            FastAPI and recorded against the
            signed-in user.
          </p>
        </div>

        <div className="workspace-user">
          <span>
            {user.role.replaceAll(
              "_",
              " ",
            )}
          </span>
          <strong>{user.email}</strong>
        </div>
      </div>

      {feedback && (
        <div
          className={
            feedback.kind === "success"
              ? "operation-feedback operation-feedback-success"
              : "operation-feedback operation-feedback-error"
          }
          role="status"
        >
          {feedback.message}
        </div>
      )}

      <div
        className={
          pendingAction || isRefreshing
            ? "operations-grid operations-grid-busy"
            : "operations-grid"
        }
        aria-busy={
          Boolean(
            pendingAction ||
            isRefreshing,
          )
        }
      >
        <article className="panel operation-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Case ownership
              </div>
              <h3>Review controls</h3>
            </div>
            {reviewCase && (
              <StatusBadge
                value={reviewCase.status}
              />
            )}
          </div>

          {!reviewCase ? (
            <p className="muted-copy">
              No human review case exists for
              this invoice.
            </p>
          ) : (
            <>
              <dl className="operation-summary">
                <div>
                  <dt>Priority</dt>
                  <dd>{reviewCase.priority}</dd>
                </div>
                <div>
                  <dt>Owner</dt>
                  <dd>
                    {reviewCase.claimed_by_email ??
                      "Unclaimed"}
                  </dd>
                </div>
                <div>
                  <dt>Version</dt>
                  <dd>{reviewCase.version}</dd>
                </div>
                <div>
                  <dt>Document</dt>
                  <dd>
                    {humanize(
                      documentStatus,
                    )}
                  </dd>
                </div>
              </dl>

              <div className="operation-button-row">
                {reviewerRole &&
                  reviewCase.status ===
                    "OPEN" && (
                    <button
                      type="button"
                      className="primary-action"
                      disabled={
                        pendingAction !== null
                      }
                      onClick={() =>
                        void perform(
                          "claim",
                          `reviews/${reviewCase.id}/claim`,
                          undefined,
                          "Review case claimed.",
                        )
                      }
                    >
                      Claim case
                    </button>
                  )}

                {canManageClaimedCase && (
                  <>
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={
                        pendingAction !== null
                      }
                      onClick={() =>
                        void perform(
                          "release",
                          `reviews/${reviewCase.id}/release`,
                          undefined,
                          "Review case released.",
                        )
                      }
                    >
                      Release
                    </button>

                    <button
                      type="button"
                      className="secondary-action"
                      disabled={
                        pendingAction !== null
                      }
                      onClick={() =>
                        void perform(
                          "rerun",
                          `reviews/${reviewCase.id}/rerun`,
                          undefined,
                          "Controls rerun.",
                        )
                      }
                    >
                      Rerun controls
                    </button>
                  </>
                )}
              </div>

              {reviewSnapshot?.latest_control_run && (
                <div className="control-run-card">
                  <div>
                    <span>
                      Latest control run
                    </span>
                    <strong>
                      {
                        reviewSnapshot
                          .latest_control_run
                          .policy_version
                      }
                    </strong>
                  </div>
                  <StatusBadge
                    value={
                      reviewSnapshot
                        .latest_control_run
                        .outcome ??
                      reviewSnapshot
                        .latest_control_run
                        .status
                    }
                  />
                  {reviewSnapshot
                    .latest_control_run
                    .blocking_reasons
                    .length > 0 && (
                    <p>
                      {reviewSnapshot
                        .latest_control_run
                        .blocking_reasons
                        .join(", ")}
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </article>

        {reviewCase && (
          <article className="panel operation-panel">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Collaboration
                </div>
                <h3>Add review note</h3>
              </div>
            </div>

            <form
              className="operation-form"
              onSubmit={submitNote}
            >
              <label>
                <span>Note</span>
                <textarea
                  name="note"
                  required
                  maxLength={2000}
                  placeholder="Record evidence or a supplier follow-up."
                />
              </label>

              <button
                type="submit"
                className="primary-action"
                disabled={
                  pendingAction !== null
                }
              >
                Add note
              </button>
            </form>
          </article>
        )}

        {reviewCase && activeCase && (
          <article className="panel operation-panel operation-panel-wide">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Controlled correction
                </div>
                <h3>Correction workspace</h3>
              </div>
              <span className="panel-note">
                Proposed values stay audited
              </span>
            </div>

            <form
              className="operation-form operation-form-grid"
              onSubmit={submitCorrection}
            >
              <label>
                <span>Target</span>
                <select
                  name="target_type"
                  value={correctionTarget}
                  onChange={(event) =>
                    setCorrectionTarget(
                      event.target.value as
                        "HEADER" |
                        "LINE_ITEM",
                    )
                  }
                >
                  <option value="HEADER">
                    Invoice header
                  </option>
                  <option value="LINE_ITEM">
                    Line item
                  </option>
                </select>
              </label>

              {correctionTarget ===
                "LINE_ITEM" && (
                <label>
                  <span>Invoice line</span>
                  <select
                    name="line_item_id"
                    required
                  >
                    <option value="">
                      Select line
                    </option>
                    {lineItems.map(
                      (line) => (
                        <option
                          key={line.id}
                          value={line.id}
                        >
                          {line.line_number}
                          {" · "}
                          {line.description}
                        </option>
                      ),
                    )}
                  </select>
                </label>
              )}

              <label>
                <span>Field</span>
                <select
                  name="field_name"
                >
                  {(correctionTarget ===
                  "HEADER"
                    ? HEADER_FIELDS
                    : LINE_FIELDS
                  ).map((field) => (
                    <option
                      key={field}
                      value={field}
                    >
                      {humanize(field)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Corrected value</span>
                <input
                  name="corrected_value"
                  required
                  placeholder="Verified value"
                />
              </label>

              <label className="operation-form-span">
                <span>Reason</span>
                <textarea
                  name="reason"
                  minLength={5}
                  maxLength={1000}
                  required
                  placeholder="Explain how this value was verified."
                />
              </label>

              <button
                type="submit"
                className="primary-action"
                disabled={
                  pendingAction !== null
                }
              >
                Propose correction
              </button>
            </form>

            {effectiveInvoice && (
              <div className="effective-values">
                <h4>
                  Current effective header
                </h4>
                <div className="effective-grid">
                  {HEADER_FIELDS.map(
                    (field) => (
                      <div key={field}>
                        <span>
                          {humanize(field)}
                        </span>
                        <strong>
                          {displayValue(
                            effectiveInvoice
                              .effective
                              .header[
                                field as keyof typeof effectiveInvoice.effective.header
                              ],
                          )}
                        </strong>
                      </div>
                    ),
                  )}
                </div>
              </div>
            )}
          </article>
        )}

        {reviewCase &&
          reviewSnapshot &&
          reviewSnapshot.corrections
            .length > 0 && (
            <article className="panel operation-panel operation-panel-wide">
              <div className="panel-header">
                <div>
                  <div className="panel-kicker">
                    Correction ledger
                  </div>
                  <h3>
                    Proposed and applied changes
                  </h3>
                </div>
              </div>

              <div className="correction-list">
                {reviewSnapshot.corrections.map(
                  (correction) => (
                    <div
                      key={correction.id}
                      className="correction-row"
                    >
                      <div>
                        <strong>
                          {correctionLabel(
                            correction,
                          )}
                        </strong>
                        <span>
                          {displayValue(
                            correction.original_value,
                          )}
                          {" → "}
                          {displayValue(
                            correction.corrected_value,
                          )}
                        </span>
                        <small>
                          {correction.reason}
                        </small>
                      </div>

                      <div className="correction-actions">
                        <StatusBadge
                          value={correction.status}
                        />

                        {correction.status ===
                          "PROPOSED" &&
                          canManageClaimedCase && (
                            <>
                              <button
                                type="button"
                                className="compact-action"
                                disabled={
                                  pendingAction !==
                                  null
                                }
                                onClick={() =>
                                  void perform(
                                    `apply-${correction.id}`,
                                    `reviews/${reviewCase.id}/corrections/${correction.id}/apply`,
                                    undefined,
                                    "Correction applied and controls rerun.",
                                  )
                                }
                              >
                                Apply
                              </button>

                              <button
                                type="button"
                                className="compact-action compact-action-danger"
                                disabled={
                                  pendingAction !==
                                  null
                                }
                                onClick={() => {
                                  const reason =
                                    window.prompt(
                                      "Rejection reason (minimum 10 characters)",
                                    );

                                  if (
                                    reason &&
                                    reason.trim()
                                      .length >= 10
                                  ) {
                                    void perform(
                                      `reject-${correction.id}`,
                                      `reviews/${reviewCase.id}/corrections/${correction.id}/reject`,
                                      {
                                        reason:
                                          reason.trim(),
                                      },
                                      "Correction rejected.",
                                    );
                                  }
                                }}
                              >
                                Reject
                              </button>
                            </>
                          )}
                      </div>
                    </div>
                  ),
                )}
              </div>
            </article>
          )}

        {reviewCase &&
          canManageClaimedCase && (
            <article className="panel operation-panel">
              <div className="panel-header">
                <div>
                  <div className="panel-kicker">
                    Final decision
                  </div>
                  <h3>Resolve case</h3>
                </div>
              </div>

              <form
                className="operation-form"
                onSubmit={submitResolution}
              >
                <label>
                  <span>Resolution</span>
                  <select
                    name="resolution"
                    defaultValue="APPROVE"
                  >
                    <option value="APPROVE">
                      Approve invoice
                    </option>
                    <option value="REJECT">
                      Reject invoice
                    </option>
                  </select>
                </label>

                <label>
                  <span>Resolution note</span>
                  <textarea
                    name="note"
                    minLength={10}
                    maxLength={2000}
                    required
                    placeholder="Document the evidence and final decision."
                  />
                </label>

                <button
                  type="submit"
                  className="primary-action"
                  disabled={
                    pendingAction !== null
                  }
                >
                  Resolve case
                </button>
              </form>
            </article>
          )}

        <article className="panel operation-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Accounting output
              </div>
              <h3>Generate export</h3>
            </div>
          </div>

          <p className="muted-copy">
            Approved invoices can be rendered
            as deterministic JSON or CSV.
          </p>

          <div className="operation-button-row">
            {(["JSON", "CSV"] as const).map(
              (format) => (
                <button
                  key={format}
                  type="button"
                  className={
                    format === "JSON"
                      ? "primary-action"
                      : "secondary-action"
                  }
                  disabled={
                    pendingAction !== null
                  }
                  onClick={() =>
                    void perform(
                      `export-${format}`,
                      `documents/${documentId}/exports`,
                      {
                        export_format:
                          format,
                      },
                      `${format} export ready.`,
                    )
                  }
                >
                  Generate
                  {" "}
                  {format}
                </button>
              ),
            )}
          </div>

          <div className="compact-list">
            {exports.map((item) => (
              <div
                key={item.id}
                className="compact-row"
              >
                <div>
                  <strong>
                    {item.export_format}
                    {" export"}
                  </strong>
                  <span>
                    {formatDateTime(
                      item.requested_at,
                    )}
                  </span>
                </div>

                <div className="compact-row-actions">
                  <StatusBadge
                    value={item.status}
                  />
                  {item.status === "READY" && (
                    <a
                      className="compact-action"
                      href={`/api/operations/exports/${item.id}/download`}
                    >
                      Download
                    </a>
                  )}
                </div>
              </div>
            ))}

            {exports.length === 0 && (
              <p className="muted-copy">
                No exports generated yet.
              </p>
            )}
          </div>
        </article>

        <article className="panel operation-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Delivery
              </div>
              <h3>Send export</h3>
            </div>
          </div>

          <form
            className="operation-form"
            onSubmit={submitDelivery}
          >
            <label>
              <span>Ready export</span>
              <select
                name="export_id"
                required
                disabled={
                  readyExports.length === 0
                }
              >
                <option value="">
                  Select export
                </option>
                {readyExports.map(
                  (item) => (
                    <option
                      key={item.id}
                      value={item.id}
                    >
                      {item.export_format}
                      {" · "}
                      {item.file_name ??
                        item.id}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label>
              <span>Channel</span>
              <select
                name="channel"
                defaultValue="EMAIL"
              >
                <option value="EMAIL">
                  Email
                </option>
                <option value="WEBHOOK">
                  Webhook
                </option>
              </select>
            </label>

            <label>
              <span>Destination</span>
              <input
                name="destination"
                required
                minLength={3}
                placeholder="ap-team@example.test or approved webhook URL"
              />
            </label>

            <button
              type="submit"
              className="primary-action"
              disabled={
                pendingAction !== null ||
                readyExports.length === 0
              }
            >
              Queue delivery
            </button>
          </form>

          <div className="compact-list">
            {notifications.map(
              (item) => (
                <div
                  key={item.id}
                  className="compact-row"
                >
                  <div>
                    <strong>
                      {humanize(item.channel)}
                      {" · "}
                      {item.destination}
                    </strong>
                    <span>
                      {item.attempt_count}
                      /
                      {item.max_attempts}
                      {" attempts"}
                    </span>
                    {item.last_error_message && (
                      <small>
                        {item.last_error_message}
                      </small>
                    )}
                  </div>

                  <div className="compact-row-actions">
                    <StatusBadge
                      value={item.status}
                    />

                    {user.role === "ADMIN" &&
                      item.status ===
                        "FAILED" && (
                        <button
                          type="button"
                          className="compact-action"
                          disabled={
                            pendingAction !==
                            null
                          }
                          onClick={() => {
                            if (
                              window.confirm(
                                "Retry this failed delivery?",
                              )
                            ) {
                              void perform(
                                `retry-${item.id}`,
                                `notifications/${item.id}/retry`,
                                undefined,
                                "Delivery requeued.",
                              );
                            }
                          }}
                        >
                          Retry
                        </button>
                      )}
                  </div>
                </div>
              ),
            )}

            {notifications.length === 0 && (
              <p className="muted-copy">
                No delivery attempts yet.
              </p>
            )}
          </div>
        </article>

        {reviewSnapshot && (
          <article className="panel operation-panel operation-panel-wide">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Immutable evidence
                </div>
                <h3>Audit trail</h3>
              </div>
              <span className="panel-note">
                {reviewSnapshot.events.length}
                {" events"}
              </span>
            </div>

            <ol className="audit-timeline">
              {reviewSnapshot.events
                .slice()
                .reverse()
                .map((event) => (
                  <li key={event.id}>
                    <div className="timeline-marker" />
                    <div>
                      <div className="timeline-heading">
                        <strong>
                          {humanize(
                            event.event_type,
                          )}
                        </strong>
                        <span>
                          {formatDateTime(
                            event.created_at,
                          )}
                        </span>
                      </div>
                      <p>{event.message}</p>
                      <small>
                        {event.actor_email ??
                          event.actor_type}
                        {event.actor_role
                          ? ` · ${event.actor_role}`
                          : ""}
                      </small>
                    </div>
                  </li>
                ))}
            </ol>
          </article>
        )}
      </div>
    </section>
  );
}
