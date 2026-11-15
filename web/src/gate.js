// Client mirror of src/btqc/uncertainty/gate.py (requirement R4): the flag
// depends only on the score and the review limit. A missing or NaN score is
// flagged (fail-safe). A score equal to the limit is not flagged.
export const NEEDS_REVIEW = 'Needs review';
export const LOOKS_RELIABLE = 'Looks reliable';

export function flag(score, reviewLimit) {
  if (typeof reviewLimit !== 'number' || Number.isNaN(reviewLimit)) throw new Error('review limit must be a number');
  if (typeof score !== 'number' || Number.isNaN(score)) return true;
  return score > reviewLimit;
}

export function decide(score, reviewLimit) {
  const f = flag(score, reviewLimit);
  let reason;
  if (typeof score !== 'number' || Number.isNaN(score)) reason = 'No uncertainty score could be computed (for example an empty prediction), so this case needs review.';
  else if (f) reason = `Boundary uncertainty ${score.toFixed(3)} is above the review limit ${reviewLimit.toFixed(3)}. A reviewer should check the outline before it is used.`;
  else reason = `Boundary uncertainty ${score.toFixed(3)} is at or below the review limit ${reviewLimit.toFixed(3)}. A routine check is enough.`;
  return { flag: f, label: f ? NEEDS_REVIEW : LOOKS_RELIABLE, reason };
}
