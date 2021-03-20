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
    case 'VIDEO_DELETED':
      state.videoList.splice(action.payload, 1)
      return {...state};
    case 'VIDEOLIST_LOADED':
      const videos = {};
      for (let i = 0; i < action.payload.length; ++i) {
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

  const deleteClicked = event => {
    fetch(`/videos/${video.id}`, {method: 'DELETE'})
      .then(dispatchState({type: 'VIDEO_DELETED', payload: video.id}));
  };

  return (
    <div className="Video">
      <span className="VideoThumbnailWrapper">
        <a href={`https://youtu.be/${video.id}`}>
          <img className="VideoThumbnail" src={video.meta.thumbnail} />
        </a>
      </span>
      <span className="VideoMetadata">
        <span className="VideoTitle">
          <a href={`https://youtu.be/${video.id}`}>{video.meta.title}</a>
        </span>
        <span>
          <label>Filename:</label>
          <span className={`VideoPath ${dirtyClass}`}>{video.relpath}</span>
          <a href={`/player/${video.id}`} target="new"><button type="button">Player</button></a>
          <a href={`/videos/${video.id}`} target="new"><button type="button">JSON</button></a>
          <a href={`/videos/${video.id}/ffprobe`} target="new"><button type="button">ffprobe</button></a>
          <button type="button" onClick={deleteClicked}>Delete video</button>
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
  fetch('/subdirs')
    .then(response => response.json())
    .then(response => dispatchState({type: 'SUBDIRS_LOADED', payload: response}))
    .then(() => {
      const encodedSubdir = encodeURIComponent(state.currentSubdir);
      fetch(`/videos?subdir=${encodedSubdir}`)
        .then(response => response.json())
        .then(response => dispatchState({type: 'VIDEOLIST_LOADED', payload: response}));
    });
}

const DragTarget = ({state, dispatchState}) => {
  const [url, setUrl] = React.useState("youtu.be/sfwMulCeHNw")

  function handleDragOver(event) {
    // console.debug(event);
    event.preventDefault();
  }

  function handleChange(event) {
    // console.debug(event);
    event.preventDefault();
    const draggedUrl = event.dataTransfer.getData("text");
    download(draggedUrl);
  }

  function download(url, subdir) {
    const params = {
      method: "POST",
      body: JSON.stringify({"url": url, "subdir": state.currentSubdir}),
      headers: {"Content-Type": "application/json"},
    };
    const target = document.querySelector("#drag-target");
    fetch("/videos", params)
      .then(response => {
        target.classList.add("success");
        setTimeout(() => target.classList.remove("success"), 1000);
      })
      .catch(error => {
        console.debug("error", error);
        target.classList.add("failure");
        setTimeout(() => target.classList.remove("failure"), 1000);
      });
  }

  const handleUrlChange = event => setUrl(event.target.value);
  const handleClick = event => download(url);

  return (
    <div className="Video" onDrop={handleChange} onDragOver={handleDragOver} >
      <div id="drag-target" className="target VideoThumbnailWrapper">
      </div>
      <div className="VideoMetadata">
        <p>
        Drag and drop a YouTube video from <a href="https://www.youtube.com/feed/history">your history</a> here to add it to the cache.
        </p>
        <p>
          Alternatively, enter a YouTube URL and click Add:
          <input type="text" value={url} onChange={handleUrlChange} />
          <button type="button" onClick={handleClick}>Add</button>
        </p>
      </div>
    </div>
  );
};

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
      <h1>Muchacho</h1>
      <SubdirSelector state={state} dispatchState={dispatchState} />
      <h2>{state.currentSubdir} Videos</h2>
      <div className="VideoList">
        <DragTarget state={state} dispatchState={dispatchState} />
        {state.videoList.map(v => <Video key={`Video_${v.id}`} video={v} state={state} dispatchState={dispatchState} />)}
      </div>
    </div>
  );
}

ReactDOM.render(<App />, document.querySelector('#app'));
