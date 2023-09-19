<template>
  <div class="h-full w-full p-4" @contextmenu="toggleEmptyContext">
    <FolderContentsError
      v-if="$resources.folderContents.error"
      :error="$resources.folderContents.error" />

    <GridView
      v-else-if="$store.state.view === 'grid'"
      :folder-contents="$resources.folderContents.data"
      :selected-entities="selectedEntities"
      @entity-selected="(selected) => (selectedEntities = selected)"
      @open-entity="(entity) => openEntity(entity)"
      @show-entity-context="(event) => toggleEntityContext(event)"
      @show-empty-entity-context="(event) => toggleEmptyContext(event)"
      @close-context-menu-event="closeContextMenu"
      @fetch-folder-contents="() => $resources.folderContents.fetch()">
      <template #toolbar>
        <DriveToolBar
          :action-items="actionItems"
          :column-headers="columnHeaders"
          :show-info-button="showInfoButton" />
      </template>
      <template #placeholder>
        <NoFilesSection />
      </template>
    </GridView>

    <ListView
      v-else
      :folder-contents="$resources.folderContents.data"
      :selected-entities="selectedEntities"
      @entity-selected="(selected) => (selectedEntities = selected)"
      @open-entity="(entity) => openEntity(entity)"
      @show-entity-context="(event) => toggleEntityContext(event)"
      @show-empty-entity-context="(event) => toggleEmptyContext(event)"
      @close-context-menu-event="closeContextMenu"
      @fetch-folder-contents="() => $resources.folderContents.fetch()">
      <template #toolbar>
        <DriveToolBar
          :action-items="actionItems"
          :column-headers="columnHeaders"
          :show-info-button="showInfoButton" />
      </template>
      <template #placeholder>
        <NoFilesSection />
      </template>
    </ListView>

    <FilePreview
      v-if="showPreview"
      :preview-entity="previewEntity"
      @hide="hidePreview" />
    <EntityContextMenu
      v-if="showEntityContext"
      v-on-outside-click="closeContextMenu"
      :entity-name="selectedEntities[0].name"
      :action-items="isLoggedIn ? actionItems : guestActionItems"
      :entity-context="entityContext"
      :close="closeContextMenu" />
    <EmptyEntityContextMenu
      v-if="showEmptyEntityContextMenu && isLoggedIn"
      v-on-outside-click="closeContextMenu"
      :action-items="emptyActionItems"
      :entity-context="entityContext"
      :close="closeContextMenu" />
    <NewFolderDialog
      v-model="showNewFolderDialog"
      :parent="$route.params.entityName"
      @success="
        () => {
          emitter.emit('fetchFolderContents');
          showNewFolderDialog = false;
        }
      " />
    <RenameDialog
      v-model="showRenameDialog"
      :entity="selectedEntities[0]"
      @success="
        () => {
          $resources.folderContents.fetch();
          showRenameDialog = false;
          selectedEntities = [];
        }
      " />
    <GeneralDialog
      v-model="showRemoveDialog"
      :entities="selectedEntities"
      :for="'remove'"
      @success="
        () => {
          $resources.folderContents.fetch();
          showRemoveDialog = false;
          selectedEntities = [];
        }
      " />
    <ShareDialog
      v-if="showShareDialog"
      v-model="showShareDialog"
      :entity-name="shareName"
      @success="$resources.folderContents.fetch()" />
  </div>
</template>

<script>
import ListView from "@/components/ListView.vue";
import GridView from "@/components/GridView.vue";
import DriveToolBar from "@/components/DriveToolBar.vue";
import NoFilesSection from "@/components/NoFilesSection.vue";
import FilePreview from "@/components/FilePreview.vue";
import NewFolderDialog from "@/components/NewFolderDialog.vue";
import RenameDialog from "@/components/RenameDialog.vue";
import ShareDialog from "@/components/ShareDialog.vue";
import GeneralDialog from "@/components/GeneralDialog.vue";
import FolderContentsError from "@/components/FolderContentsError.vue";
import EntityContextMenu from "@/components/EntityContextMenu.vue";
import EmptyEntityContextMenu from "@/components/EmptyEntityContextMenu.vue";
import { formatSize, formatDate } from "@/utils/format";
import {
  folderDownload,
  selectedEntitiesDownload,
} from "@/utils/folderDownload";

export default {
  name: "Folder",
  components: {
    ListView,
    GridView,
    DriveToolBar,
    NoFilesSection,
    FilePreview,
    NewFolderDialog,
    RenameDialog,
    ShareDialog,
    GeneralDialog,
    FolderContentsError,
    EntityContextMenu,
    EmptyEntityContextMenu,
  },
  props: {
    entityName: {
      type: String,
      required: false,
      default: "",
    },
  },
  data: () => ({
    selectedEntities: [],
    previewEntity: null,
    showPreview: false,
    showRenameDialog: false,
    showShareDialog: false,
    showRemoveDialog: false,
    showEntityContext: false,
    showEmptyEntityContextMenu: false,
    showNewFolderDialog: false,
    entityContext: {},
    breadcrumbs: [{ label: "Folder", route: "/folder" }],
    isSharedFolder: false,
  }),
  computed: {
    isLoggedIn() {
      return this.$store.getters.isLoggedIn;
    },
    userId() {
      return this.$store.state.auth.user_id;
    },
    showInfoButton() {
      return !!this.selectedEntities.length && !this.$store.state.showInfo;
    },
    orderBy() {
      return this.$store.state.sortOrder.ascending
        ? this.$store.state.sortOrder.field
        : `${this.$store.state.sortOrder.field} desc`;
    },
    shareName() {
      return this.selectedEntities[0]
        ? this.selectedEntities[0].name
        : this.entityName;
    },
    emptyActionItems() {
      return [
        {
          label: "Subir Archivo",
          icon: "file",
          handler: () => this.emitter.emit("uploadFile"),
          isEnabled: () => this.selectedEntities.length === 0,
        },
        {
          label: "Subir Carpeta",
          icon: "folder",
          handler: () => this.emitter.emit("uploadFolder"),
          isEnabled: () => this.selectedEntities.length === 0,
        },
        {
          label: "Nueva Carpeta",
          icon: "folder-plus",
          handler: () => (this.showNewFolderDialog = true),
          isEnabled: () => this.selectedEntities.length === 0,
        },
        {
          label: "Nuevo Documento",
          icon: "file-text",
          handler: () => this.newDocument(),
          isEnabled: () => this.selectedEntities.length === 0,
        },
        {
          label: "Pegar",
          icon: "clipboard",
          handler: async () => {
            this.pasteEntities(this.entityName);
          },
          isEnabled: () =>
            this.$store.state.pasteData.entities.length &&
            this.$store.state.hasWriteAccess,
        },
      ].filter((item) => item.isEnabled());
    },
    actionItems() {
      return [
        {
          label: "Descargar",
          icon: "download",
          onClick: () => {
            window.location.href = `/api/method/drive.api.files.get_file_content?entity_name=${this.selectedEntities[0].name}&trigger_download=1`;
          },
          isEnabled: () => {
            if (this.selectedEntities.length === 1) {
              return (
                this.selectedEntities[0].allow_download &&
                !this.selectedEntities[0].is_group &&
                !this.selectedEntities[0].document
              );
            }
          },
        },
        {
          label: "Descargar como ZIP",
          icon: "download",
          onClick: () => {
            if (this.selectedEntities.length > 1) {
              let selected_entities = this.selectedEntities;
              selectedEntitiesDownload(selected_entities);
            } else if (this.selectedEntities[0].is_group === 1) {
              folderDownload(this.selectedEntities[0]);
            }
          },
          isEnabled: () => {
            if (
              this.selectedEntities.length === 1 &&
              !this.selectedEntities[0].is_group
            ) {
              return false;
            }
            if (this.selectedEntities.length) {
              const allEntitiesSatisfyCondition = this.selectedEntities.every(
                (entity) => {
                  return (
                    entity.allow_download ||
                    entity.write ||
                    entity.owner === "me"
                  );
                }
              );
              return allEntitiesSatisfyCondition;
            }
          },
        },
        {
          label: "Compartir",
          icon: "share-2",
          onClick: () => {
            this.showShareDialog = true;
          },
          isEnabled: () => {
            return this.selectedEntities.length === 1;
          },
        },
        {
          label: "Ver detalles",
          icon: "eye",
          onClick: () => {
            this.$store.commit("setShowInfo", true);
          },
          isEnabled: () => {
            return (
              !this.$store.state.showInfo && this.selectedEntities.length === 1
            );
          },
        },
        {
          label: "Ocultar detalles",
          icon: "eye-off",
          onClick: () => {
            this.$store.commit("setShowInfo", false);
          },
          isEnabled: () => {
            return this.$store.state.showInfo;
          },
        },
        {
          label: "Renombrar",
          icon: "edit",
          onClick: () => {
            this.showRenameDialog = true;
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length === 1 &&
              (this.selectedEntities[0].write ||
                this.selectedEntities[0].owner === "me")
            );
          },
        },
        {
          label: "Cortar",
          icon: "scissors",
          onClick: () => {
            this.$store.commit("setPasteData", {
              entities: this.selectedEntities.map((x) => x.name),
              action: "cut",
            });
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length > 0 &&
              this.selectedEntities.every((x) => x.owner === "me" || x.write)
            );
          },
        },
        {
          label: "Copiar",
          icon: "copy",
          onClick: () => {
            this.$store.commit("setPasteData", {
              entities: this.selectedEntities.map((x) => x.name),
              action: "copy",
            });
          },
          isEnabled: () => {
            return this.selectedEntities.length > 0;
          },
        },
        {
          label: "Pegar en carpeta",
          icon: "clipboard",
          onClick: async () => {
            this.pasteEntities(this.selectedEntities[0].name);
          },
          isEnabled: () => {
            return (
              this.$store.state.pasteData.entities.length &&
              this.selectedEntities.length === 1 &&
              this.selectedEntities[0].is_group &&
              (this.selectedEntities[0].write ||
                this.selectedEntities[0].owner === "me")
            );
          },
        },
        {
          label: "Agregar a favoritos",
          icon: "star",
          onClick: () => {
            this.$resources.toggleFavourite.submit();
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length > 0 &&
              this.selectedEntities.every((x) => !x.is_favourite)
            );
          },
        },
        {
          label: "Eliminar de favoritos",
          icon: "x-circle",
          onClick: () => {
            this.$resources.toggleFavourite.submit();
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length > 0 &&
              this.selectedEntities.every((x) => x.is_favourite)
            );
          },
        },
        {
          label: "Cambiar de color",
          icon: "droplet",
          isEnabled: () => {
            return (
              this.selectedEntities.length === 1 &&
              this.selectedEntities[0].is_group
            );
          },
        },
        {
          label: "Eliminar",
          icon: "trash-2",
          onClick: () => {
            this.$resources.removeEntity.submit();
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length > 0 &&
              this.selectedEntities.every((x) => x.owner != "me") &&
              (this.selectedEntities.every((x) => x.write) ||
                !this.isSharedFolder)
            );
          },
        },
        {
          label: "Mover a la Papelera",
          icon: "trash-2",
          onClick: () => {
            this.showRemoveDialog = true;
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length > 0 &&
              this.selectedEntities.every((x) => x.owner === "me")
            );
          },
        },
      ].filter((item) => item.isEnabled());
    },
    guestActionItems() {
      return [
        {
          label: "Descargar",
          icon: "download",
          onClick: () => {
            window.location.href = `/api/method/drive.api.files.get_file_content?entity_name=${this.selectedEntities[0].name}&trigger_download=1`;
          },
          isEnabled: () => {
            if (this.selectedEntities.length === 1) {
              if (
                this.selectedEntities[0].allow_download &&
                this.selectedEntities.length === 1 &&
                !this.selectedEntities[0].is_group
              ) {
                return !this.selectedEntities[0].document;
              }
            }
          },
        },
        {
          label: "Descargar como ZIP",
          icon: "download",
          onClick: () => {
            if (this.selectedEntities.length > 1) {
              let selected_entities = this.selectedEntities;
              selectedEntitiesDownload(selected_entities);
            } else if (this.selectedEntities[0].is_group === 1) {
              folderDownload(this.selectedEntities[0]);
            }
          },
          isEnabled: () => {
            if (
              this.selectedEntities[0].allow_download &&
              this.selectedEntities.length === 1 &&
              !this.selectedEntities[0].is_group
            ) {
              return false;
            }
            if (this.selectedEntities.length) {
              const allEntitiesSatisfyCondition = this.selectedEntities.every(
                (entity) => {
                  return (
                    entity.allow_download ||
                    entity.write ||
                    entity.owner === "me"
                  );
                }
              );
              return allEntitiesSatisfyCondition;
            }
          },
        },
        {
          label: "Ver detalles",
          icon: "eye",
          onClick: () => {
            this.$store.commit("setShowInfo", true);
          },
          isEnabled: () => {
            return (
              !this.$store.state.showInfo && this.selectedEntities.length === 1
            );
          },
        },
        {
          label: "Ocultar detalles",
          icon: "eye-off",
          onClick: () => {
            this.$store.commit("setShowInfo", false);
          },
          isEnabled: () => {
            return this.$store.state.showInfo;
          },
        },
        {
          label: "Renombrar",
          icon: "edit",
          onClick: () => {
            this.showRenameDialog = true;
          },
          isEnabled: () => {
            return (
              this.selectedEntities.length === 1 &&
              (this.selectedEntities[0].write ||
                this.selectedEntities[0].owner === "me")
            );
          },
        },
        {
          label: "Cambiar color",
          icon: "droplet",
          isEnabled: () => {
            return (
              this.selectedEntities.length === 1 &&
              this.selectedEntities[0].is_group &&
              this.selectedEntities[0].write
            );
          },
        },
      ].filter((item) => item.isEnabled());
    },
    columnHeaders() {
      return [
        {
          label: "Nombre",
          field: "title",
          sortable: true,
        },
        {
          label: "Propietario",
          field: "owner",
          sortable: true,
        },
        {
          label: "Modificado",
          field: "modified",
          sortable: true,
        },
        {
          label: "Tamaño",
          field: "file_size",
          sortable: true,
        },
      ].filter((item) => item.sortable);
    },
  },
  watch: {
    async entityName() {
      await this.$resources.folderAccess.fetch();
      this.$store.commit(
        "setHasWriteAccess",
        !!this.$resources.folderAccess.data?.write
      );
      this.selectedEntities = [];
    },
  },

  async mounted() {
    this.pasteListener = (e) => {
      if (
        (e.ctrlKey || e.metaKey) &&
        (e.key === "v" || e.key === "V") &&
        this.$store.state.pasteData.entities.length &&
        this.$store.state.hasWriteAccess
      )
        this.pasteEntities(this.entityName);
    };
    window.addEventListener("keydown", this.pasteListener);

    this.deleteListener = (e) => {
      if (
        e.key === "Delete" &&
        this.selectedEntities.length &&
        this.selectedEntities.every((x) => x.owner === "me")
      )
        this.showRemoveDialog = true;
    };
    window.addEventListener("keydown", this.deleteListener);
    window.addEventListener(
      "dragover",
      function (e) {
        e = e || event;
        e.preventDefault();
      },
      false
    );
    window.addEventListener(
      "drop",
      function (e) {
        e = e || event;
        e.preventDefault();
      },
      false
    );

    await this.$resources.folderAccess.fetch();
    this.$store.commit(
      "setHasWriteAccess",
      !!this.$resources.folderAccess.data?.write
    );
    let componentContext = this;
    this.emitter.on("fetchFolderContents", () => {
      componentContext.$resources.folderContents.fetch();
    });
  },
  async updated() {
    await this.$store.commit("setCurrentFolderID", this.entityName);
  },
  unmounted() {
    window.removeEventListener("keydown", this.pasteListener);
    window.removeEventListener("keydown", this.deleteListener);
    this.$store.commit("setHasWriteAccess", false);
  },
  methods: {
    openEntity(entity) {
      if (entity.is_group) {
        this.selectedEntities = [];
        this.$router.push({
          name: "Folder",
          params: { entityName: entity.name },
        });
      } else {
        this.$router.push({
          name: "File",
          params: { entityName: entity.name },
        });
        this.previewEntity = entity;
        this.showPreview = true;
      }
    },

    async pasteEntities(newParent = null) {
      const method =
        this.$store.state.pasteData.action === "cut" ? "move" : "copy";
      for (let i = 0; i < this.$store.state.pasteData.entities.length; i++) {
        await this.$resources.pasteEntity.submit({
          method,
          entity_name: this.$store.state.pasteData.entities[i],
          new_parent: newParent,
        });
      }
      this.selectedEntities = [];
      this.$store.commit("setPasteData", { entities: [], action: null });
      this.$resources.folderContents.fetch();
    },

    hidePreview() {
      this.showPreview = false;
      this.previewEntity = null;
    },

    toggleEntityContext(event) {
      if (!event) this.showEntityContext = false;
      else {
        this.hidePreview();
        this.showEntityContext = true;
        this.showEmptyEntityContextMenu = false;
        this.entityContext = event;
      }
    },
    toggleEmptyContext(event) {
      if (!event) {
        this.showEntityContext = false;
        this.showEmptyEntityContextMenu = false;
      } else if (this.selectedEntities.length === 0) {
        this.selectedEntities = [];
        this.hidePreview();
        this.showEntityContext = false;
        this.showEmptyEntityContextMenu = true;
        this.entityContext = event;
      }
    },
    closeContextMenu() {
      this.showEntityContext = false;
      this.showEmptyEntityContextMenu = false;
      this.entityContext = undefined;
    },
    triggerFetchFolderEmit() {
      this.emitter.emit("fetchFolderContents");
    },
    async newDocument() {
      await this.$resources.createDocument.submit({
        title: "Untitled Document",
        content: null,
        parent: this.$store.state.currentFolderID,
      });
      this.$router.push({
        name: "Document",
        params: { entityName: this.previewEntity.name },
      });
    },
  },

  resources: {
    folderAccess() {
      return {
        url: "drive.api.permissions.get_user_access",
        params: { entity_name: this.entityName },
      };
    },

    // createFolder() {
    //   return {
    //     url: "drive.api.files.create_folder",
    //     params: {
    //       title: this.folderName,
    //       parent: this.parent,
    //     },
    //     validate(params) {
    //       if (!params?.title) {
    //         return "Folder name is required";
    //       }
    //     },
    //     onSuccess() {
    //       this.$resources.folderContents.fetch();
    //     },
    //     onError(error) {
    //       if (error.messages) {
    //         this.errorMessage = error.messages.join("\n");
    //       } else {
    //         this.errorMessage = error.message;
    //       }
    //     },
    //   };
    // },

    pasteEntity() {
      return {
        url: "drive.api.files.call_controller_method",
        method: "POST",
        validate(params) {
          if (!params?.new_parent) {
            return "New parent is required";
          }
        },
      };
    },

    folderContents() {
      return {
        url: "drive.api.files.list_folder_contents",
        // cache: ['folderContents', this.entityName],
        params: {
          entity_name: this.entityName,
          order_by: this.orderBy,
          fields:
            "name,title,is_group,owner,modified,file_size,mime_type,creation,allow_download",
        },
        onSuccess(data) {
          this.$resources.folderContents.error = null;
          data.forEach((entity) => {
            entity.size_in_bytes = entity.file_size;
            entity.file_size = entity.is_group
              ? entity.item_count + " items"
              : formatSize(entity.file_size);
            entity.modified = formatDate(entity.modified);
            entity.creation = formatDate(entity.creation);
            entity.owner = entity.owner === this.userId ? "me" : entity.owner;
          });
        },
        auto: true,
      };
    },

    pathEntities() {
      return {
        url: "drive.api.files.get_entity",
        // cache: ['pathEntities', this.entityName],
        params: {
          entity_name: this.entityName,
          fields: "title",
        },
        onSuccess(data) {
          this.isSharedFolder = data.is_shared;
          let currentBreadcrumbs = this.$store.state.currentBreadcrumbs;
          // Duplicate folder in breadcrumb but unique entity ID
          const index = currentBreadcrumbs.findIndex(
            (item) => item.route === "/folder/" + this.entityName
          );
          if (index !== -1) {
            const slicedBreadCrumb = currentBreadcrumbs.slice(0, index + 1);
            this.$store.commit("setCurrentBreadcrumbs", slicedBreadCrumb);
          } else {
            currentBreadcrumbs.push({
              label: data.title,
              route: `/folder/${this.entityName}`,
            });
          }
        },
        auto: Boolean(this.entityName),
      };
    },

    toggleFavourite() {
      return {
        url: "drive.api.files.add_or_remove_favourites",
        params: {
          entity_names: JSON.stringify(
            this.selectedEntities?.map((entity) => entity.name)
          ),
        },
        onSuccess() {
          this.$resources.folderContents.fetch();
          this.selectedEntities = [];
        },
        onError(error) {
          if (error.messages) {
            console.log(error.messages);
          }
        },
      };
    },

    createDocument() {
      return {
        url: "drive.api.files.create_document_entity",
        onSuccess(data) {
          data.modified = formatDate(data.modified);
          data.creation = formatDate(data.creation);
          this.$store.commit("setEntityInfo", [data]);
          this.previewEntity = data;
          data.owner = "me";
        },
        onError(data) {
          console.log(data);
        },
        auto: false,
      };
    },

    removeEntity() {
      return {
        url: "drive.api.files.unshare_entities",
        params: {
          entity_names: JSON.stringify(
            this.selectedEntities.map((entity) => entity.name)
          ),
          move: true,
        },
        onSuccess() {
          this.$resources.folderContents.fetch();
        },
        onError(error) {
          if (error.messages) {
            console.log(error.messages);
          }
        },
      };
    },
  },
};
</script>
