# Pollen comes from Google, not Open-Meteo

How's It Outside? gets its weather and air quality from Open-Meteo, free and keyless, but its pollen from the Google Pollen API, which needs a Google Cloud key on a billing account. Open-Meteo does list pollen fields (ragweed, grass, birch and others), but they come from the CAMS European model and are empty for US locations: a request for a New York point returned `null` for every pollen field while its AQI was filled (checked 2026-10-31). Google is the only free-to-use US source found that names individual plants, such as oak or ragweed, which matters for someone who reacts to trees in particular.

The cost is a second provider with a key and a billing account. Pollen is daily data, so it is fetched once a day and cached, about 31 requests a month against Google's free 5,000 (checked 2026-10-31).

## Considered Options

- **Open-Meteo pollen**: no key and one provider, but no US data.
- **Tomorrow.io**: free tier and hourly, but only tree, grass and weed totals, with no plant names.
- **Pollen.com**: names the day's top allergens, but only through an unofficial endpoint with unclear terms, which breaks easily.
