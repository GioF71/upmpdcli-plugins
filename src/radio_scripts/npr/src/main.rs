use hyper::{Client, Uri};
use serde::{Serialize,Deserialize,Deserializer};
use std::env;
use chrono::offset::{FixedOffset,TimeZone,Utc};
use chrono::naive::{NaiveDateTime};
use chrono::{Duration};

// Begin JavaScript serialization structs

#[derive(Deserialize, Debug)]
struct ZoneInfo {
    offset: i32,
}

#[derive(Deserialize, Debug)]
struct Ucs {
    #[serde(rename = "_zoneInfo")]
    zone_info: ZoneInfo,
}

#[derive(Deserialize, Debug)]
struct Program {
    name: String,
}

#[derive(Deserialize, Debug)]
struct Song {
    #[serde(rename = "trackName")]
    track_name: String,
    #[serde(rename = "artistName")]
    artist_name: String,

    #[serde(default)]
    #[serde(rename = "collectionName")]
    collection_name: String,

    #[serde(rename = "_start_time")]
    start: String,

    #[serde(deserialize_with = "deserialize_duration")]
    #[serde(rename = "_duration")]
    duration: Duration,
}
impl Default for Song {
    fn default() -> Self {
	Song {
	    track_name: "NOSONG".to_string(),
	    artist_name: "NOSONG".to_string(),
	    collection_name: "NOSONG".to_string(),
	    start: "01-01-1970 00:00:00".to_string(),
	    duration: Duration::seconds(10),
	}
    }
}
fn deserialize_duration<'de, D>(deserializer: D) -> Result<Duration, D::Error>
where D: Deserializer<'de>
{
    let millis: i64 = Deserialize::deserialize(deserializer)?;
    Ok(Duration::milliseconds(millis))
}

#[derive(Deserialize, Debug)]
struct OnNow {
    #[serde(default)]
    song: Song,

    #[serde(rename = "start_utc")]
    start: String,
    #[serde(rename = "end_utc")]
    end: String,

    program: Program,
}

#[derive(Deserialize, Debug)]
struct Input {
    #[serde(rename = "onNow")]
    on_now: OnNow,

    ucs: Ucs,
}

#[derive(Serialize, Debug)]
struct Output {
    title: String,
    reload: i64,
    album: String,
    artist: String,
}

// End JavaScript serialization structs


#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {


    // Identify argument with station ID
    let mut argv = env::args();
    argv.next(); // ignore program name
    let stationid = argv.next().unwrap();
    // println!("stationref = {:?}", stationid);

    // Assemble the API URL
    let uristr = format!("http://api.composer.nprstations.org/v1/widget/{}/now?format=json",stationid);
    let uri = uristr.parse::<Uri>().unwrap();

    // TODO: use TLS
    // TODO: use clientbuilder and requestbuilder
    // TODO: follow iTunes link to extract album art URL, cache locally so artScript doesn't have to call this API again

    // Make the request
    let client = Client::new();
    let res = client.get(uri).await?;

    let body_bytes = hyper::body::to_bytes(res.into_body()).await?;

    let input: Input = serde_json::from_slice(&body_bytes)?;
    // println!("input JSON: {:?}", input);

    // Normalize song time and time zone to UTC
    let offset = FixedOffset::east(input.ucs.zone_info.offset * 60 * 60);
    let naivesongstart =
	NaiveDateTime::parse_from_str(input.on_now.song.start.as_str(),
				      "%m-%d-%Y %H:%M:%S")?;
    // println!("{:?}",naivesongstart);
    let songstart = offset.from_local_datetime(&naivesongstart).unwrap();
    let songstart = songstart.with_timezone(&Utc); // Convert FixedOffset to Utc so add/subract work

    // Try to identify how much time is left in the current song.  If we
    // can't determine when to reload, just do it every 30s
    let now = Utc::now();
    let songend = songstart + input.on_now.song.duration;
    let reload = songend - now;
    let reload = reload + Duration::seconds(15); // pad some to avoid negative
    let mut reload = reload.num_seconds(); // int not Duration
    if reload < 0 {
	reload = 30;
    }

    // Assemble the output as expected by upmpdcli
    let mut output = Output {
	title: input.on_now.song.track_name,
	reload: reload,
	album: input.on_now.song.collection_name,
	artist: input.on_now.song.artist_name,
    };

    // Fall back to program name if no song
    if output.title == "NOSONG" {
	output.title = input.on_now.program.name.clone();
	output.artist = input.on_now.program.name.clone();
    }

    // Output the song information for upmdcli
    println!("{}",serde_json::to_string(&output).unwrap());

    Ok(())
}
