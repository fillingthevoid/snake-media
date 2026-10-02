const input = $('Integration Input').first().json;
const data = $input.first().json;
const fail = status => [{json:{version:1,status}}];
if (!data || data.error) return fail('error');
if (!Object.keys(data).length) return fail('not_found');
const mediaType = input.mediaType;
if (!['movie','tv'].includes(mediaType)) return fail('error');
const external = mediaType === 'movie' ? data.tmdbId : data.tvdbId;
if (!Number.isSafeInteger(data.id) || data.id < 1 || !Number.isSafeInteger(external) || external < 1 || typeof data.title !== 'string' || !data.title.trim()) return fail('error');
const result = {version:1,status:data.status === 'already_added' ? 'already_added':'added',mediaType,title:data.title.trim(),mediaId:String(data.id),externalId:String(external),searchStarted:data.status !== 'already_added',context:input.context,raw:data};
const poster = (data.images || []).find(x=>x.coverType === 'poster');
const url = poster?.remoteUrl || poster?.url;
// Only public metadata artwork; never send LAN URLs or credential-bearing URLs.
if (typeof url === 'string' && /^https:\/\/(image\.tmdb\.org|artworks\.thetvdb\.com)\/[A-Za-z0-9_./%~-]+$/.test(url) && url.length <= 2048) result.posterUrl=url;
return [{json:result}];
