# 30-second video: draft script (T23)

Rules: 30 s maximum, English subtitles, visible watermark on any AI-generated image/video, no NASA logos, declare AI use. Body of the video = screen recording of the real app.

The rescue route is the main feature, so it gets the most screen time.

| Time | Screen | Voice-over / subtitle (draft) |
|---|---|---|
| 0-4 s | App step 1: clouds covering the map | "January 2026, Mozambique. Clouds hid the flood from optical satellites." |
| 4-9 s | Step 2/3: clouds lift, red new-water layer, before/after slider | "NISAR's radar sees through clouds: 982 square kilometres of new water." |
| 9-24 s | Step 5: click the team's base, click a point inside the flood. Route appears: car leg along the dry road, boat icon at the water's edge, dashed boat leg to the pin. Scroll the step-by-step directions | "Rescue teams pick a base and a target in the flood. We drive them on roads the radar saw dry, launch the boat at the water's edge and guide them in." |
| 24-27 s | Toggle "Car only", then back to "Car and boat"; show the grey alternative lines | "Car only or car and boat, with every option on the map." |
| 27-30 s | Closing card: team name, link | "The Algorithm's Oracle. Open source." |

Notes
- 982 km² is the real value in `outputs/stats.json` (`flooded_area_km2: 982.5`). Re-check it if the detection is rerun.
- Good demo trip: base in Chókwè (`33.004, -24.530`), destination `33.0206, -24.7070`. It gives 29.3 km by car and 2.8 km by boat, launched south of Chókwè.
- The rescue step needs the Flask app with `outputs/routing_network.npz`; the static GitHub Pages copy has no routes. Record from `python app\app.py`.
- Total spoken text is about 70 words, which fits 30 s at a brisk pace. Trim the 9-24 s line if it runs long.
- Jhuan edits. Any AI intro/outro must be watermarked and logged in `AI_USAGE_LOG.md`.
