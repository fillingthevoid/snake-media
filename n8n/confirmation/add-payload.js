// Build nested payloads in Code, away from n8n's template expression delimiters.
const r=$('Confirmed Metadata').first().json;
const m=r.media;
if(!m||typeof m.title!=='string'||!m.title.trim())throw new Error('Missing confirmed title');
if(r.mediaType==='movie'){
 if(!Number.isSafeInteger(m.tmdbId)||m.tmdbId<=0)throw new Error('Invalid confirmed movie');
 return [{json:{title:m.title,tmdbId:m.tmdbId,year:m.year,qualityProfileId:4,rootFolderPath:'/movies',monitored:true,minimumAvailability:'released',addOptions:{searchForMovie:false}}}];
}
if(r.mediaType!=='tv'||!Number.isSafeInteger(m.tvdbId)||m.tvdbId<=0||!Array.isArray(m.seasons))throw new Error('Invalid confirmed series');
return [{json:{title:m.title,tvdbId:m.tvdbId,titleSlug:m.titleSlug,qualityProfileId:4,rootFolderPath:'/tv',monitored:false,monitorNewItems:'none',seasonFolder:true,seriesType:m.seriesType||'standard',seasons:m.seasons.map(s=>({seasonNumber:s.seasonNumber,monitored:false})),addOptions:{monitor:'none',searchForMissingEpisodes:false,searchForCutoffUnmetEpisodes:false}}}];
