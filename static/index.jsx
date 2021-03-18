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
      const videos = {};
      for (let i = 0; i < action.payload.length; ++i) {
        action.payload[i].meta = null;
        videos[action.payload[i].id] = i;
      }
      return {
        ...state,
        videoList: action.payload,
        videos: videos,
      };
    case 'SUBDIRS_LOADED':
      return {
        ...state,
        allSubdirs: action.payload,
      }
    default:
      throw new Error(`unsupported action.type: ${action.type}`);
  }
}

const Video = ({video, state, dispatchState}) => {
  console.debug('Video', video);
  const [selection, setSelection] = React.useState(state.currentSubdir);
  const [formatstr, setFormatstr] = React.useState(video.filename);
  const [dirty, setDirty] = React.useState(false);

  let thumbnail = "https://via.placeholder.com/200x133";
  if (video.meta) {
    thumbnail = video.meta.thumbnail;
  }
  
  function validateFormatstr(formatstr) {
    formatstr = encodeURIComponent(formatstr);
    const url = `/videos/${video.id}/preview_relpath?formatstr=${formatstr}`;
    fetch(url)
      .then(response => response.json())
      .then(response => {
        dispatchState(
          {
            type: 'PATH_UPDATED',
            payload: {videoid: video.id, path: response.relpath}
          }
        );
      });
  }

  const handleChange = event => {
    setFormatstr(event.target.value);
    validateFormatstr(event.target.value);
    setDirty(true);
  };

  function renameVideo(newName) {
    const url = `/videos/${video.id}`;
    const params = {
      method: 'PUT',
      body: JSON.stringify({relpath: newName}),
      headers: {'Content-Type': 'application/json'},
    };
    fetch(url, params)
      .then(response => response.json())
      .then(response => {
        dispatchState(
          {
            type: 'PATH_UPDATED',
            payload: {videoid: video.id, path: response.relpath}
          }
        );
      })
      .then(() => setDirty(false));
  }

  const handleRenameClicked = event => renameVideo(video.relpath);

  let dirtyClass = dirty ? "dirty" : "";
  const handleSelect = event => {console.debug('handleSelect', event.target.value); setSelection(event.target.value)};
  const handleMoveClicked = event => renameVideo(selection);

  function applyPreset(preset) {
    setFormatstr(preset);
    validateFormatstr(preset);
    setDirty(true);
  }

  const handleFilenameClicked = event => {console.debug(video); applyPreset(video.filename)};
  const handleTitleClicked = event => applyPreset("%(title)s.%(ext)s");
  const handleDateClicked = event => applyPreset("%(upload_date)s.%(ext)s");

  let title = "";
  if (video.meta) {
    title = video.meta.title;
  }

  return (
    <div className="Video">
      <span className="VideoThumbnailWrapper">
        <a href={`https://youtu.be/${video.id}`}>
          <img className="VideoThumbnail" src={thumbnail} />
        </a>
      </span>
      <span className="VideoMetadata">
        <span className="VideoTitle">
          <a href={`https://youtu.be/${video.id}`}>{title}</a>
        </span>
        <span>
          <label>Filename:</label>
          <span className={`VideoPath ${dirtyClass}`}>{video.relpath}</span>
        </span>
        <span className="VideoMover">
          <label>Move to:</label>
          <select onChange={handleSelect} value={selection} >
            {state.allSubdirs.map(subdir => <option key={`Video_${video.id}_subdir_${subdir.name}`} >{subdir.name}</option>)}
          </select>
          <button type="button" onClick={handleMoveClicked} disabled={selection === video.subdir}>Move</button>
        </span>
        <span className="VideoRenamer">
          <span>Rename presets:</span>
          <button type="button" onClick={handleFilenameClicked}>Filename</button>
          <button type="button" onClick={handleTitleClicked}>Title</button>
          <button type="button" onClick={handleDateClicked}>Date</button>
        </span>
        <span className="VideoFormatstr">
          <span>formatstr:</span>
          <input type="text" placeholder="formatstr" onChange={handleChange} value={formatstr} />
          <button type="button" onClick={handleRenameClicked}>Rename</button>
        </span>
      </span>
      
    </div>
  );
};

const SubdirSelector = ({state, dispatchState}) => {
  // TODO: show a graphical layout of existing prefixes as well as text entry
  const [text, setText] = React.useState("unsorted");

  const handleChange = event => {
    console.debug('SubdirSelector.handleChange', event.target.value);
    setText(event.target.value);
  };

  const handleSubmit = event => {
    dispatchState({type: 'CURRENT_SUBDIR_UPDATED', payload: text});
    event.preventDefault();
  };

  const handleClick = event => {
    console.debug('SubdirSelector.handleClick', event.target.textContent)
    dispatchState({type: 'CURRENT_SUBDIR_UPDATED', payload: event.target.textContent});
  };

  return (
    <div className="SubdirSelector">
      <form>
        <input type="text" onChange={handleChange} value={text} />
        <button type="submit" onClick={handleSubmit}>Go</button>
      </form>
      <ul>
        {state.allSubdirs.map(subdir => <button type="button" key={`SubdirSelector_${subdir.name}`} onClick={handleClick} >{subdir.name}</button>)}
      </ul>
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

  fetch('/subdirs')
    .then(response => response.json())
    .then(response => dispatchState({type: 'SUBDIRS_LOADED', payload: response}));
}

function App() {
  const defaultState = {
    videoList: [],
    currentSubdir: 'unsorted',
    allSubdirs: [],
  };
  const [state, dispatchState] = React.useReducer(reducer, defaultState);

  React.useEffect(() => loadSubdir(state, dispatchState), [state.currentSubdir]);

  return (
    <div>
      <SubdirSelector state={state} dispatchState={dispatchState} />
      <h2>{state.currentSubdir} Videos</h2>
      <div className="VideoList">
        {state.videoList.map(v => <Video key={`Video_${v.id}`} video={v} state={state} dispatchState={dispatchState} />)}
      </div>
    </div>
  );
}

ReactDOM.render(<App />, document.querySelector('#app'));
