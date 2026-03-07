// Format: project@priority@title@notes
// Example: btc@P2@Fix reconnect jitter@check startup burst behavior

let raw = draft.content.trim();
let parts = raw.split("@");

if (parts.length < 3) {
	context.fail("Use format: project@priority@title@notes");
} else {
	let project = parts[0].trim().toLowerCase();
	let priority = parts[1].trim().toUpperCase();
	let title = parts[2].trim();
	let notes = parts.slice(3).join("@").trim();

	let endpoint = "https://your-domain/td-capture?token=REPLACE_WITH_REAL_TOKEN";

	let http = HTTP.create();
	let resp = http.request({
		url: endpoint,
		method: "POST",
		data: {
			project: project,
			priority: priority,
			title: title,
			notes: notes
		},
		encoding: "json"
	});

	if (resp.statusCode >= 200 && resp.statusCode < 300) {
		app.displaySuccessMessage("Queued to TD");
	} else {
		context.fail("HTTP " + resp.statusCode + ": " + resp.responseText);
	}
}
