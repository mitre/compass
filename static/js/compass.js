function generateLayer() {
    function downloadObjectAsJson(data){
        let exportName = 'layer';
        let dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
        let downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", exportName + ".json");
        document.body.appendChild(downloadAnchorNode); // required for firefox
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    }

    let postData = {'all': true};
    restRequest('POST', postData, downloadObjectAsJson, '/plugin/compass/layer');
}