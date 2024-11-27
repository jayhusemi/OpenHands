import React from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "#/context/auth-context";
import { useUserPrefs } from "#/context/user-prefs-context";
import { useGitHubUser } from "#/hooks/query/use-github-user";
import { useIsAuthed } from "#/hooks/query/use-is-authed";
import { AllHandsLogoButton } from "#/components/ui/buttons/all-hands-logo-button";
import { DocsButton } from "#/components/ui/buttons/docs-button";
import { SettingsButton } from "#/components/ui/buttons/settings-button";
import { AccountSettingsModal } from "#/components/modals/account-settings/account-settings-modal";
import { SettingsModal } from "#/components/modals/settings/settings-modal";
import { UserActions } from "./user-actions";
import { ExitProjectButton } from "../../ui/buttons/exit-project-button";
import { ExitProjectConfirmationModal } from "#/components/modals/exit-project-confirmation-modal";
import { LoadingSpinner } from "#/components/ui/loading-spinner";

export function Sidebar() {
  const location = useLocation();

  const user = useGitHubUser();
  const { data: isAuthed } = useIsAuthed();

  const { token, logout } = useAuth();
  const { settingsAreUpToDate } = useUserPrefs();

  const [accountSettingsModalOpen, setAccountSettingsModalOpen] =
    React.useState(false);
  const [settingsModalIsOpen, setSettingsModalIsOpen] = React.useState(false);
  const [startNewProjectModalIsOpen, setStartNewProjectModalIsOpen] =
    React.useState(false);

  React.useEffect(() => {
    // If the github token is invalid, open the account settings modal again
    if (user.isError) {
      setAccountSettingsModalOpen(true);
    }
  }, [user.isError]);

  const handleAccountSettingsModalClose = () => {
    // If the user closes the modal without connecting to GitHub,
    // we need to log them out to clear the invalid token from the
    // local storage
    if (user.isError) logout();
    setAccountSettingsModalOpen(false);
  };

  const handleClickLogo = () => {
    if (location.pathname.startsWith("/app"))
      setStartNewProjectModalIsOpen(true);
  };

  const showSettingsModal =
    isAuthed && (!settingsAreUpToDate || settingsModalIsOpen);

  return (
    <>
      <aside className="px-1 flex flex-col gap-1">
        <div className="w-[34px] h-[34px] flex items-center justify-center">
          {user.isLoading && <LoadingSpinner size="small" />}
          {!user.isLoading && <AllHandsLogoButton onClick={handleClickLogo} />}
        </div>

        <nav className="py-[18px] flex flex-col items-center gap-[18px]">
          <UserActions
            user={user.data ? { avatar_url: user.data.avatar_url } : undefined}
            onLogout={logout}
            onClickAccountSettings={() => setAccountSettingsModalOpen(true)}
          />
          <SettingsButton onClick={() => setSettingsModalIsOpen(true)} />
          <DocsButton />
          {!!token && (
            <ExitProjectButton
              onClick={() => setStartNewProjectModalIsOpen(true)}
            />
          )}
        </nav>
      </aside>
      {accountSettingsModalOpen && (
        <AccountSettingsModal onClose={handleAccountSettingsModalClose} />
      )}
      {showSettingsModal && (
        <SettingsModal onClose={() => setSettingsModalIsOpen(false)} />
      )}
      {startNewProjectModalIsOpen && (
        <ExitProjectConfirmationModal
          onClose={() => setStartNewProjectModalIsOpen(false)}
        />
      )}
    </>
  );
}
