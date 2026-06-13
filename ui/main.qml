import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami

ApplicationWindow {
    id: root
    visible: true

    title: "klut"
    minimumWidth: 1100
    minimumHeight: 700
    width: 1280
    height: 800

    property real splitPos: 0.5

    // Restore session *after* QML Connections exist
    Component.onCompleted: Backend.restoreSession()

    // Use Kirigami theme colors
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Window

    // ── File Dialogs ──
    FileDialog {
        id: imageFileDialog
        title: Backend.translate("open_image_title")
        nameFilters: [
            "Images (*.png *.jpg *.jpeg *.ppm *.tif *.bmp *.webp)",
            "All files (*)"
        ]
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            var paths = []
            for (var i = 0; i < selectedFiles.length; i++)
                paths.push(selectedFiles[i])
            Backend.openImages(paths.join(";"))
        }
    }

    FileDialog {
        id: lutFileDialog
        title: Backend.translate("open_lut_title")
        nameFilters: ["LUT Files (*.cube)", "All files (*)"]
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            var paths = []
            for (var i = 0; i < selectedFiles.length; i++)
                paths.push(selectedFiles[i])
            Backend.openLutFiles(paths.join(";"))
        }
    }

    FileDialog {
        id: exportFileDialog
        title: Backend.translate("export_title")
        nameFilters: ["PNG (*.png)", "JPEG (*.jpg)", "All files (*)"]
        fileMode: FileDialog.SaveFile
        onAccepted: Backend.exportPng(selectedFile)
    }

    // ── Keyboard shortcuts ──
    Shortcut { sequence: "O";       onActivated: imageFileDialog.open() }
    Shortcut { sequence: "L";       onActivated: lutFileDialog.open() }
    Shortcut { sequence: "E";       onActivated: exportFileDialog.open() }
    Shortcut { sequence: "W";       onActivated: Backend.toggleWatermark() }
    Shortcut { sequence: "D";       onActivated: debugPanel.visible = !debugPanel.visible }
    Shortcut { sequence: "C";       onActivated: Backend.cycleSrcCs() }
    Shortcut { sequence: "Shift+C"; onActivated: Backend.cycleLutCs() }
    Shortcut { sequence: "Up";      onActivated: Backend.prevLut() }
    Shortcut { sequence: "Down";    onActivated: Backend.nextLut() }
    Shortcut { sequence: "Left";    onActivated: Backend.prevImage() }
    Shortcut { sequence: "Right";   onActivated: Backend.nextImage() }

    // ── Menu Bar ──
    menuBar: MenuBar {
        Menu {
            title: Backend.translate("file_menu")
            Action { text: Backend.translate("open_image"); shortcut: "O"; onTriggered: imageFileDialog.open() }
            Action { text: Backend.translate("open_lut_files"); shortcut: "L"; onTriggered: lutFileDialog.open() }
            MenuSeparator {}
            Action { text: Backend.translate("export_png"); shortcut: "E"; onTriggered: exportFileDialog.open() }
            MenuSeparator {}
            Action { text: Backend.translate("quit"); shortcut: "Q"; onTriggered: Qt.quit() }
        }

        Menu {
            title: Backend.translate("view_menu")
            Action {
                text: Backend.translate("toggle_watermark"); checkable: true
                checked: Backend.showWatermark
                onTriggered: Backend.toggleWatermark()
            }
            Action {
                text: Backend.translate("toggle_debug")
                onTriggered: debugPanel.visible = !debugPanel.visible
            }
            MenuSeparator {}
            Action {
                text: Backend.translate("ext_manager")
                onTriggered: extManagerDialog.open()
            }
            MenuSeparator {}
            Menu {
                title: Backend.translate("accent_color")
                Action { text: "Orange";  onTriggered: Backend.accentColor = "#ff9900" }
                Action { text: "Blue";    onTriggered: Backend.accentColor = "#0099ff" }
                Action { text: "Green";   onTriggered: Backend.accentColor = "#00bb00" }
                Action { text: "Red";     onTriggered: Backend.accentColor = "#ff4444" }
                Action { text: "Purple";  onTriggered: Backend.accentColor = "#9900ff" }
                Action { text: "Teal";    onTriggered: Backend.accentColor = "#00ffff" }
                Action { text: "Pink";    onTriggered: Backend.accentColor = "#ff00ff" }
            }
            MenuSeparator {}
            Menu {
                title: Backend.translate("language")
                Action { text: "中文";    onTriggered: {} }
                Action { text: "English"; onTriggered: {} }
            }
        }

        // Extensions — top-level menu bar entry
        Menu {
            id: extMenu
            title: Backend.translate("ext_menu")

            Instantiator {
                model: ListModel { id: _extMenuModel }
                delegate: Action {
                    text: model.name
                    onTriggered: Backend.launchExtension(model.extId)
                }
                onObjectAdded: function(index, object) {
                    extMenu.insertAction(index, object);
                }
                onObjectRemoved: function(index, object) {
                    extMenu.removeAction(object);
                }
            }

            MenuSeparator {}
            Action {
                text: Backend.translate("ext_manager")
                onTriggered: extManagerDialog.open()
            }

            Component.onCompleted: _reloadExtensions()

            function _reloadExtensions() {
                _extMenuModel.clear();
                var exts = Backend.extensionList();
                for (var i = 0; i < exts.length; i++) {
                    if (exts[i].type !== "python")
                        continue;
                    _extMenuModel.append({
                        name: exts[i].name,
                        extId: exts[i].id,
                        description: exts[i].description
                    });
                }
            }
        }

        Menu {
            title: Backend.translate("color_menu")
            Action { text: Backend.translate("cycle_src_cs"); shortcut: "C";       onTriggered: Backend.cycleSrcCs() }
            Action { text: Backend.translate("cycle_lut_cs"); shortcut: "Shift+C"; onTriggered: Backend.cycleLutCs() }
        }
    }

    // ── Main Content ──
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Toolbar
        ToolBar {
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent; spacing: 6

                Button {
                    text: Backend.translate("open"); icon.name: "document-open"
                    onClicked: imageFileDialog.open()
                }
                Button {
                    text: Backend.translate("luts"); icon.name: "folder-open"
                    onClicked: lutFileDialog.open()
                }
                Button {
                    text: Backend.translate("export"); icon.name: "document-save"
                    onClicked: exportFileDialog.open()
                }
                Button {
                    text: Backend.translate("wm")
                    checkable: true; checked: Backend.showWatermark
                    onClicked: Backend.toggleWatermark()
                }
                Button {
                    text: Backend.translate("debug")
                    checkable: true; checked: debugPanel.visible
                    onClicked: debugPanel.visible = !debugPanel.visible
                }

                // Image navigation in toolbar
                Button {
                    text: "◀"
                    flat: true
                    font.pixelSize: 16
                    enabled: Backend.currentImageIndex > 0
                    visible: Backend.imageCount > 1
                    onClicked: Backend.prevImage()
                }
                Label {
                    text: (Backend.currentImageIndex + 1) + "/" + Backend.imageCount
                    font.pixelSize: 11
                    visible: Backend.imageCount > 1
                }
                Button {
                    text: "▶"
                    flat: true
                    font.pixelSize: 16
                    enabled: Backend.currentImageIndex < Backend.imageCount - 1
                    visible: Backend.imageCount > 1
                    onClicked: Backend.nextImage()
                }

                Item { Layout.fillWidth: true }

                Label {
                    text: Backend.translate("preview_limit") + " " + Backend.maxPreview
                    font.pixelSize: 11
                }
                Slider {
                    from: 256; to: 4096; stepSize: 64
                    value: Backend.maxPreview
                    Layout.preferredWidth: 120
                    onMoved: Backend.maxPreview = value
                }
            }
        }

        // ── Body: Preview + LUT Panel ──
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            visible: true

            // ═══ Preview Column ═══
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // Split-screen preview — rendered by Python's
                // _render_combined() with cycling filenames so QML
                // always reloads the combined image.
                Item {
                    id: previewContainer
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.bottomMargin: 6
                    clip: true

                    // Original image — fills the container as background
                    Image {
                        id: origImg
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        source: Backend.imageCount > 0 && Backend.currentImageIndex >= 0
                                ? "file://" + Backend.imagePath(Backend.currentImageIndex)
                                : ""
                        visible: source !== ""
                        asynchronous: true
                    }

                    // LUT image — overlaid and clipped to right portion of split
                    Item {
                        id: lutClip
                        x: root.splitPos * parent.width
                        width: parent.width - x
                        height: parent.height
                        clip: true
                        visible: Backend.lutImagePath !== "" && Backend.imageCount > 0

                        Image {
                            x: -lutClip.x
                            y: 0
                            width: previewContainer.width
                            height: previewContainer.height
                            fillMode: Image.PreserveAspectFit
                            source: Backend.lutImagePath !== ""
                                    ? "file://" + Backend.lutImagePath : ""
                            asynchronous: true
                        }
                    }

                    // Split line
                    Rectangle {
                        x: root.splitPos * parent.width - 1
                        y: 0; width: 2; height: parent.height
                        color: Backend.accentColor
                        visible: lutClip.visible
                    }

                    // Drag handle
                    Rectangle {
                        x: root.splitPos * parent.width - 14
                        y: parent.height / 2 - 14
                        width: 28; height: 28; radius: 14
                        color: Backend.accentColor
                        border.color: "#fff"; border.width: 2
                        visible: lutClip.visible
                        Text {
                            anchors.centerIn: parent
                            text: "◀▶"; color: "#1a1a2e"
                            font.bold: true; font.pixelSize: 10
                        }
                    }

                    // Drag MouseArea — only updates local splitPos
                    MouseArea {
                        id: splitDrag
                        anchors.fill: parent
                        enabled: Backend.imageCount > 0 && Backend.lutCount > 0
                        cursorShape: Qt.SplitHCursor
                        onPositionChanged: {
                            if (pressed)
                                root.splitPos = Math.max(0.02, Math.min(0.98,
                                    mouseX / previewContainer.width))
                        }
                    }
                    // Empty state
                    Text {
                        anchors.centerIn: parent
                        text: Backend.translate("open_hint"); color: "#555"
                        font.pixelSize: 14
                        visible: Backend.imageCount === 0
                    }

                    // Watermark (only when both image and LUT available)
                    Rectangle {
                        id: wmBox
                        visible: Backend.showWatermark && Backend.lutCount > 0 && Backend.imageCount > 0
                        anchors.top: parent.top; anchors.topMargin: 8
                        anchors.right: parent.right; anchors.rightMargin: 8
                        width: 200; height: 34; color: Qt.rgba(0, 0, 0, 0.7)
                        Rectangle {
                            anchors.top: parent.top; anchors.left: parent.left
                            anchors.right: parent.right; height: 3
                            color: Backend.accentColor
                        }
                        Text {
                            x: 6; y: 4
                            text: Backend.translate("lut_prefix") + " " + Backend.currentLutName
                            color: "#fff"; font.pixelSize: 11
                        }
                        Text {
                            x: 6; y: 18
                            text: Backend.srcCsName + " → " + Backend.lutCsName
                            color: "#888"; font.pixelSize: 8
                        }
                    }
                }

                // Thumbnail bar — horizontal scrollable list
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 84
                    color: "transparent"
                    visible: Backend.imageCount > 1

                    ListView {
                        anchors.fill: parent; anchors.margins: 8
                        orientation: ListView.Horizontal; spacing: 8
                        model: Backend.imageCount; clip: true

                        delegate: Rectangle {
                            width: thumbImg.width + 4; height: thumbImg.height + 4
                            color: index === Backend.currentImageIndex
                                   ? Qt.rgba(1, 0.67, 0.2, 0.08) : "transparent"
                            border.width: 2
                            border.color: index === Backend.currentImageIndex
                                          ? Backend.accentColor : "transparent"
                            radius: 4
                            Image {
                                id: thumbImg; x: 2; y: 2
                                source: "file://" + Backend.imagePath(index)
                                fillMode: Image.PreserveAspectFit
                                sourceSize.width: 80; sourceSize.height: 64
                                asynchronous: true
                            }
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: Backend.selectImage(index)
                            }
                        }

                        ScrollBar.horizontal: ScrollBar {}
                    }
                }
            }

            // ═══ LUT Panel ═══
            Rectangle {
                Layout.preferredWidth: 270
                Layout.fillHeight: true
                color: Kirigami.Theme.backgroundColor

                ColumnLayout {
                    anchors.fill: parent; spacing: 0

                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 40
                        color: Qt.darker(Kirigami.Theme.backgroundColor, 1.1)
                        Label {
                            anchors.centerIn: parent
                            text: Backend.translate("luts_title")
                            color: Backend.accentColor; font.bold: true; font.pixelSize: 13
                        }
                    }

                    // LUT list — ListModel populated via Connections to
                    // avoid Qt 6 integer-model binding issues.
                    ListView {
                        id: lutListView
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true

                        model: ListModel { id: lutListModel }
                        delegate: ItemDelegate {
                            width: ListView.view.width
                            text: model.name
                            highlighted: model.idx === Backend.currentLutIndex
                            background: Rectangle {
                                color: model.idx === Backend.currentLutIndex
                                    ? Qt.rgba(1, 0.67, 0.2, 0.1)
                                    : (model.idx % 2 === 0 ? "transparent" : Qt.rgba(1, 1, 1, 0.03))
                            }
                            onClicked: Backend.selectLut(model.idx)
                        }

                        ScrollBar.vertical: ScrollBar {}
                    }
                    Connections {
                        target: Backend
                        function onLutListChanged() {
                            lutListModel.clear()
                            for (var i = 0; i < Backend.lutCount; i++)
                                lutListModel.append({
                                    "name": Backend.lutName(i),
                                    "idx": i
                                })
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 120
                        color: Qt.darker(Kirigami.Theme.backgroundColor, 1.05)

                        GridLayout {
                            anchors.fill: parent; anchors.margins: 12
                            columns: 2; rowSpacing: 6; columnSpacing: 8

                            Label { text: Backend.translate("source_cs"); font.pixelSize: 11 }
                            ComboBox {
                                Layout.fillWidth: true
                                model: Backend.colorspaceNames()
                                currentIndex: Backend.srcCsIndex
                                onCurrentIndexChanged: Backend.setSrcCs(currentIndex)
                            }

                            Label { text: Backend.translate("lut_cs"); font.pixelSize: 11 }
                            ComboBox {
                                Layout.fillWidth: true
                                model: Backend.colorspaceNames()
                                currentIndex: Backend.lutCsIndex
                                onCurrentIndexChanged: Backend.setLutCs(currentIndex)
                            }

                            Item { Layout.preferredHeight: 1 }
                            CheckBox {
                                text: Backend.translate("watermark")
                                checked: Backend.showWatermark
                                onToggled: Backend.toggleWatermark()
                            }
                        }
                    }
                }
            }
        }

        // ── Debug panel ──
        Rectangle {
            id: debugPanel
            Layout.fillWidth: true
            Layout.preferredHeight: 150
            visible: false
            color: "#0a0a0a"
            border.color: "#333"

            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8
                Label { text: "Debug"; color: "#f90"; font.bold: true }
                ScrollView {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    TextArea {
                        id: debugText; readOnly: true; color: "#aaa"
                        font.family: "monospace"; font.pixelSize: 10; background: null
                    }
                }
            }

            Connections {
                target: Backend
                function onDebugLog(msg, level) {
                    var colors = { "info": "#aaa", "warn": "#f90", "error": "#f44" }
                    var c = colors[level] || "#aaa"
                    var t = new Date().toLocaleTimeString(Qt.locale(), "hh:mm:ss")
                    debugText.append("<span style='color:" + c + "'>[" + t + "] " + msg + "</span>")
                }
            }
        }
    }

    // ── Extension Manager Dialog ──
    Dialog {
        id: extManagerDialog
        title: "Extension Manager"; modal: true; standardButtons: Dialog.Close
        width: 620; height: 450
        onOpened: _refreshExtList()
        onClosed: extListModel.clear()
        contentItem: ColumnLayout {
            spacing: 6

            Label { text: "Installed Extensions"; font.bold: true }

            ListView {
                id: extManagerList
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true
                model: ListModel { id: extListModel }
                delegate: RowLayout {
                    width: extManagerList.width
                    spacing: 6

                    ItemDelegate {
                        Layout.fillWidth: true
                        text: model.name + "  v" + model.version
                              + "  [" + model.type + "]\n  " + model.description
                    }

                    Button {
                        text: "📦 .lutx"
                        flat: true
                        enabled: model.type === "python"
                        onClicked: {
                            exportLutxFileDialog.extId = model.id;
                            exportLutxFileDialog.currentFile = model.id + ".lutx";
                            exportLutxFileDialog.open();
                        }
                    }
                }
                ScrollBar.vertical: ScrollBar {}
            }

            Button {
                text: "📥 Import .lutx"
                Layout.alignment: Qt.AlignLeft
                onClicked: importLutxFileDialog.open()
            }
        }
    }

    // ── .lutx import / export file dialogs ──
    FileDialog {
        id: importLutxFileDialog
        title: "Import .lutx Package"
        nameFilters: ["LUTX Packages (*.lutx)", "All files (*)"]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var path = selectedFile;
            if (path) {
                Backend.importExtension(path);
                _refreshExtList();
            }
        }
    }

    FileDialog {
        id: exportLutxFileDialog
        title: "Export .lutx Package"
        nameFilters: ["LUTX Packages (*.lutx)", "All files (*)"]
        fileMode: FileDialog.SaveFile
        property string extId: ""
        onAccepted: {
            var path = selectedFile;
            if (path) {
                if (path.indexOf(".lutx") < 0)
                    path += ".lutx";
                Backend.exportExtension(extId, path);
            }
        }
    }

    // ── Helper: refresh ext list model in the manager dialog ──
    function _refreshExtList() {
        extListModel.clear();
        var exts = Backend.extensionList();
        for (var i = 0; i < exts.length; i++)
            extListModel.append(exts[i]);
    }

    // ── Status bar ──
    footer: Rectangle {
        id: statusFooter
        height: 24; color: Kirigami.Theme.backgroundColor

        Label {
            id: statusLabel
            anchors.fill: parent; anchors.leftMargin: 8
            verticalAlignment: Text.AlignVCenter; font.pixelSize: 11
            color: Kirigami.Theme.textColor
            Connections {
                target: Backend
                function onStatusChanged(msg) { statusLabel.text = msg }
            }
        }
    }
}
