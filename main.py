from moderate import run_moderate_mode
from advance import run_advance_mode
from basic import run_basic_mode


def show_menu():
    print("\n==============================")
    print("        DE-DUPLICATE")
    print("==============================\n")
    print("Advance  (a) -> Full scan device and smartly organizes files")
    print("Moderate (m) -> Organizes all types of files in 'Downloads'")
    print("Basic    (b) -> Full scan for duplicates & corrupted files ")
    print("Exit     (e) -> To exit/quit type 'e', 'exit' or 'quit'")
    print()


def main():
    while True:
        try:
            show_menu()

            choice = input("What is your choice? => ").strip().lower()
            
            if choice in ("m", "moderate"):
                run_moderate_mode()
                break
            elif choice in ("b", "basic"):
            	run_basic_mode()
            	break
            elif choice in ("a", "advance"):
                run_advance_mode()
                break 

            elif choice in ("e", "exit", "quit"):
                print("\n[INFO] Exiting program.")
                break

            else:
                print("\n[ERROR] Invalid option. Please enter 'Quick' or 'Full'.\n")

        except KeyboardInterrupt:
            print("\n\n[INFO] Interrupted by user. Exiting safely.")
            break

        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")
            print("Restarting...\n")


if __name__ == "__main__":
    main()