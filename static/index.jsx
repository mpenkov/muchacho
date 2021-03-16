function reducer(state, action) {
  console.debug('reducer action.type', action.type);
  switch (action.type) {
    case 'CURRENT_SUBDIR_UPDATED':
      return {
        ...state,
        currentSubdir: action.payload,
      };
    case 'PATH_UPDATED':
      console.debug(action);
      {
        let videoIndex = state.videos[action.payload.videoid];
        state.videoList[videoIndex].relpath = action.payload.path;
        state.videoList[videoIndex].dirtyFlag = action.payload.dirty;
      }
      return {...state};
    case 'VIDEO_LOADED':
      console.debug(action);
      {
        let videoIndex = state.videos[action.payload.id];
        state.videoList[videoIndex] = action.payload;
      }
      return {...state};
    case 'VIDEOLIST_LOADED':
      // console.debug(action);
      const videos = {};
      for (let i = 0; i < action.payload.length; ++i) {
        action.payload[i].meta = null;
        action.payload[i].dirtyFlag = false;
        videos[action.payload[i].id] = i;
      }
      return {
        ...state,
        videoList: action.payload,
        videos: videos,
      };
    default:
      throw new Error(`unsupported action.type: ${action.type}`);
  }
}

const Video = ({video, state, dispatchState}) => {
  let thumbnail = "https://via.placeholder.com/200x133";
  if (video.meta) {
    thumbnail = video.meta.thumbnail;
  }
  const handleKeyPress = event => {
    const formatstr = encodeURIComponent(event.target.value);
    const url = `/videos/${video.id}/preview_relpath?formatstr=${formatstr}`;
    // console.debug('handleKeyPress', event.target.value, url);
    fetch(url)
      .then(response => response.json())
      .then(response => {
        dispatchState(
          {
            type: 'PATH_UPDATED',
            payload: {videoid: video.id, path: response.relpath, dirty: true}
          }
        );
      });
  };
  const handleClick = event => {
    const videoIndex = state.videos[video.id];
    const url = `/videos/${video.id}`;
    const params = {
      method: 'PUT',
      body: JSON.stringify({relpath: state.videoList[videoIndex].relpath}),
      headers: {'Content-Type': 'application/json'},
    };
    fetch(url, params)
      .then(response => response.json())
      .then(response => {
        dispatchState(
          {
            type: 'PATH_UPDATED',
            payload: {videoid: video.id, path: response.relpath, dirty: false}
          }
        );
      });
  };
  let dirtyClass = video.dirtyFlag ? "dirty" : "";
  return (
    <div className="Video">
      <img className="VideoThumbnail" src={thumbnail} />
      <span className="VideoMetadata">
        <span className="VideoId">{video.id}</span>
        <span className={`VideoPath ${dirtyClass}`}>{video.relpath}</span>
        <input type="text" placeholder="formatstr" onKeyUp={handleKeyPress} />
        <button type="button" onClick={handleClick}>Rename</button>
      </span>
      
    </div>
  );
};

const SubdirSelector = ({state, dispatchState}) => {
  // TODO: show a graphical layout of existing prefixes as well as text entry
  const handleChange = event => {
    console.debug('SubdirSelector.handleChange', event.target.value);
    dispatchState({type: 'CURRENT_SUBDIR_UPDATED', payload: event.target.value});
  };

  const handleClick = event => {
    console.debug('SubdirSelector.handleClick', event.target.value);
    loadSubdir(state, dispatchState);
    event.preventDefault();
  };

  return (
    <div className="SubdirSelector">
      <form>
        <input type="text" onChange={handleChange} value={state.currentSubdir} />
        <button type="submit" onClick={handleClick}>Go</button>
      </form>
    </div>
  );
};

function loadSubdir(state, dispatchState) {
  function loadVideos(videoList, index) {
    if (index < videoList.length) {
      fetch(`/videos/${videoList[index].id}`)
        .then(response => response.json())
        .then(response => {
          dispatchState({type: 'VIDEO_LOADED', payload: response});
          loadVideos(videoList, index + 1);
        });
    }
  }

  const encodedSubdir = encodeURIComponent(state.currentSubdir);
  fetch(`/videos?subdir=${encodedSubdir}`)
    .then(response => response.json())
    .then(response => {
      dispatchState({type: 'VIDEOLIST_LOADED', payload: response});
      loadVideos(response, 0);
    });
}

function App() {
  const defaultState = {
    videoList: [],
    currentSubdir: 'unsorted',
  };
  const [state, dispatchState] = React.useReducer(reducer, defaultState);

  React.useEffect(() => loadSubdir(state, dispatchState), []);

  return (
    <div>
      <h2>Videos</h2>
      <SubdirSelector state={state} dispatchState={dispatchState} />
      <div className="VideoList">
        {state.videoList.map(v => <Video key={`Video_${v.id}`} video={v} state={state} dispatchState={dispatchState} />)}
      </div>
    </div>
  );
}

ReactDOM.render(<App />, document.querySelector('#app'));
