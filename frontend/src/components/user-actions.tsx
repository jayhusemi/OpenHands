import { cn } from "@nextui-org/react";
import React from "react";
import { isGitHubErrorReponse } from "#/api/github";
import { AccountSettingsContextMenu } from "./context-menu/account-settings-context-menu";
import { LoadingSpinner } from "./modals/LoadingProject";
import DefaultUserAvatar from "#/assets/default-user.svg?react";

interface UserActionsProps {
  isLoading: boolean;
  user: GitHubUser | GitHubErrorReponse | null;
  onLogout: () => void;
  handleOpenAccountSettingsModal: () => void;
}

export function UserActions({
  isLoading,
  user,
  onLogout,
  handleOpenAccountSettingsModal,
}: UserActionsProps) {
  const [accountContextMenuIsVisible, setAccountContextMenuIsVisible] =
    React.useState(false);

  const validUser = user && !isGitHubErrorReponse(user);

  const handleClickUserAvatar = () => {
    setAccountContextMenuIsVisible((prev) => !prev);
  };

  return (
    <div className="w-8 h-8 relative">
      <button
        type="button"
        className={cn(
          "bg-white w-8 h-8 rounded-full flex items-center justify-center",
          isLoading && "bg-transparent",
        )}
        onClick={handleClickUserAvatar}
      >
        {!validUser && !isLoading && (
          <DefaultUserAvatar width={20} height={20} />
        )}
        {!validUser && isLoading && <LoadingSpinner size="small" />}
        {validUser && (
          <img
            src={user.avatar_url}
            alt="User avatar"
            className="w-full h-full rounded-full"
          />
        )}
      </button>
      {accountContextMenuIsVisible && (
        <AccountSettingsContextMenu
          isLoggedIn={!!user}
          onClose={() => setAccountContextMenuIsVisible(false)}
          onClickAccountSettings={() => {
            setAccountContextMenuIsVisible(false);
            handleOpenAccountSettingsModal();
          }}
          onLogout={() => {
            onLogout();
            setAccountContextMenuIsVisible(false);
          }}
        />
      )}
    </div>
  );
}
